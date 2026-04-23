from datetime import datetime
from peewee import *

from config.settings import settings

db = SqliteDatabase(str(settings.database_path), pragmas={"foreign_keys": 1})


class BaseModel(Model):
    class Meta:
        database = db


class Case(BaseModel):
    """案件表"""

    case_no = CharField(max_length=50, unique=True, verbose_name="案件编号")
    suspect_name = CharField(max_length=100, verbose_name="嫌疑人姓名")
    brand = CharField(max_length=100, null=True, verbose_name="涉案品牌")
    amount = DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="涉案金额"
    )
    created_at = DateTimeField(default=datetime.now, verbose_name="创建时间")

    class Meta:
        table_name = "cases"


class Person(BaseModel):
    """人员表"""

    name = CharField(max_length=100, verbose_name="姓名")
    role = CharField(max_length=50, null=True, verbose_name="角色")
    is_authorized = BooleanField(default=None, null=True, verbose_name="是否有授权")
    authorization_proof = TextField(null=True, verbose_name="授权证明")
    subjective_knowledge_score = IntegerField(default=0, verbose_name="主观明知评分")
    illegal_business_amount = DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="非法经营数额"
    )
    linked_cases = IntegerField(default=0, verbose_name="关联案件数")

    class Meta:
        table_name = "persons"


class Transaction(BaseModel):
    """资金流水表"""

    case = ForeignKeyField(Case, backref="transactions", on_delete="CASCADE")
    transaction_time = DateTimeField(verbose_name="交易时间")
    payer = CharField(max_length=100, verbose_name="打款方")
    payee = CharField(max_length=100, verbose_name="收款方")
    amount = DecimalField(max_digits=15, decimal_places=2, verbose_name="交易金额")
    payment_method = CharField(max_length=50, null=True, verbose_name="支付方式")
    remark = TextField(null=True, verbose_name="交易备注")

    class Meta:
        table_name = "transactions"


class Communication(BaseModel):
    """通讯记录表"""

    case = ForeignKeyField(Case, backref="communications", on_delete="CASCADE")
    communication_time = DateTimeField(verbose_name="联络时间")
    initiator = CharField(max_length=100, verbose_name="发起方")
    receiver = CharField(max_length=100, verbose_name="接收方")
    content = TextField(null=True, verbose_name="聊天内容")

    class Meta:
        table_name = "communications"


class Logistics(BaseModel):
    """物流记录表"""

    case = ForeignKeyField(Case, backref="logistics", on_delete="CASCADE")
    shipping_time = DateTimeField(verbose_name="发货时间")
    tracking_no = CharField(max_length=100, null=True, verbose_name="快递单号")
    sender = CharField(max_length=100, verbose_name="发件人")
    sender_address = TextField(null=True, verbose_name="发件地址")
    receiver = CharField(max_length=100, verbose_name="收件人")
    receiver_address = TextField(null=True, verbose_name="收件地址")
    description = TextField(null=True, verbose_name="物品描述")
    weight = DecimalField(
        max_digits=10, decimal_places=2, null=True, verbose_name="包裹重量"
    )

    class Meta:
        table_name = "logistics"


class SuspiciousClue(BaseModel):
    """可疑线索表"""

    case = ForeignKeyField(Case, backref="suspicious_clues", on_delete="CASCADE")
    clue_type = CharField(max_length=50, verbose_name="线索类型")
    evidence_text = TextField(verbose_name="证据原文")
    hit_keywords = TextField(null=True, verbose_name="命中关键词")
    score = IntegerField(default=0, verbose_name="评分")
    crime_type = CharField(max_length=100, null=True, verbose_name="涉嫌罪名")
    severity_level = CharField(max_length=50, null=True, verbose_name="严重程度")

    class Meta:
        table_name = "suspicious_clues"


def init_db():
    """初始化数据库表"""
    db.connect()
    db.create_tables(
        [Case, Person, Transaction, Communication, Logistics, SuspiciousClue]
    )
    db.close()
    print("数据库初始化完成")


if __name__ == "__main__":
    init_db()

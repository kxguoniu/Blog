# -*- coding: utf-8 -*-

import peewee as models
import peewee_async

database = peewee_async.PooledMySQLDatabase('blog', max_connections=10, **{'charset': 'utf8', 'use_unicode': True, 'host': '127.0.0.1', 'user': '****', 'password': '****'})

Objects = peewee_async.Manager(database)

__all__ = ["Objects","BaseModel","Permission","Group","Author","Category","Blog","Tag","Blogtag","Skynet",
            "Message","Visitor","Comment","Reply","Todolist"]

class UnknownField(object):
    def __init__(self, *_, **__): pass

class BaseModel(models.Model):
    class Meta:
        database = database

class Permission(BaseModel):
    fun_name = models.CharField(max_length=50, verbose_name=u"函数名")
    name = models.CharField(max_length=50, verbose_name=u"权限名")
    class Meta:
        table_name = 'permission'

class Group(BaseModel):
    desc = models.CharField(max_length=50, verbose_name=u"备注")
    name = models.CharField(max_length=50, verbose_name=u"用户组")
    permiss_list = models.CharField(max_length=100, verbose_name=u"权限列表")
    class Meta:
        table_name = 'group'

class Author(BaseModel):
    age = models.IntegerField(default=0, verbose_name=u'年龄')
    group = models.ForeignKeyField(Group, index=True, null=True)
    img = models.CharField(max_length=50, verbose_name=u"头像")
    name = models.CharField(max_length=50, verbose_name=u"姓名")
    passwd = models.CharField(max_length=300, verbose_name=u"密码")
    class Meta:
        table_name = 'author'

class Category(BaseModel):
    name = models.CharField(max_length=20, verbose_name=u"名称")
    class Meta:
        table_name = 'category'

class Blog(BaseModel):
    author = models.ForeignKeyField(Author, index=True, null=True)
    body = models.TextField(verbose_name=u"文章内容")
    category = models.ForeignKeyField(Category, index=True, null=True)
    change_time = models.DateTimeField(formats='%Y-%m-%d %H:%M:%S', verbose_name=u"创建时间")
    create_time = models.DateTimeField(formats='%Y-%m-%d %H:%M:%S', verbose_name=u"修改时间")
    digested = models.CharField(max_length=200, verbose_name=u"文章摘要")
    html = models.TextField(verbose_name=u"HTML内容")
    keywords = models.CharField(max_length=200, verbose_name=u"文章关键字")
    title = models.CharField(max_length=70, verbose_name=u"标题")
    views = models.IntegerField(default=0, verbose_name=u"阅读量")
    weight = models.IntegerField(default=1, verbose_name=u"权重")
    class Meta:
        table_name = 'blog'

class Tag(BaseModel):
    name = models.CharField(max_length=15, verbose_name=u"名称")
    class Meta:
        table_name = 'tag'

class Blogtag(BaseModel):
    blog = models.ForeignKeyField(Blog, index=True)
    tag = models.ForeignKeyField(Tag, index=True)
    class Meta:
        table_name = 'blogtag'

class Skynet(BaseModel):
    create_time = models.DateTimeField(formats='%Y-%m-%d %H:%M:%S', verbose_name=u"创建时间")
    free = models.IntegerField(default=0, verbose_name=u"空闲内存")
    min1 = models.FloatField(default=0, verbose_name=u"一分钟负载")
    min15 = models.FloatField(default=0, verbose_name=u"十五分钟负载")
    min5 = models.FloatField(default=0, verbose_name=u"五分钟负载")
    netin = models.IntegerField(default=0, verbose_name=u"下载流量")
    netout = models.IntegerField(default=0, verbose_name=u"上传流量")
    sycpu = models.FloatField(default=0, verbose_name=u"系统Cpu")
    total = models.IntegerField(default=0, verbose_name=u"总内存")
    uscpu = models.FloatField(default=0, verbose_name=u"用户Cpu")
    used = models.IntegerField(default=0, verbose_name=u"使用内存")
    class Meta:
        table_name = 'skynet'

class Message(BaseModel):
    content = models.CharField(max_length=300, verbose_name=u"内容")
    create_time = models.DateTimeField(formats='%Y-%m-%d %H:%M:%S', verbose_name=u"创建时间")
    fromaddr = models.CharField(max_length=100, verbose_name=u"发件人")
    status = models.IntegerField(default=0, verbose_name=u"状态")
    title = models.CharField(max_length=200, verbose_name=u"标题")
    toaddr = models.CharField(max_length=100, verbose_name=u"收件人")
    class Meta:
        table_name = 'message'

class Visitor(BaseModel):
    sums = models.IntegerField(default=0, verbose_name=u"访问量")
    time = models.DateField(formats='%Y-%m-%d', verbose_name=u"时间")
    class Meta:
        table_name = 'visitor'

class Comment(BaseModel):
    blog = models.ForeignKeyField(Blog, index=True)
    create_time = models.DateTimeField(formats='%Y-%m-%d %H:%M:%S', verbose_name=u"创建时间")
    floor = models.IntegerField(default=0, verbose_name=u"楼层")
    img = models.CharField(max_length=50, verbose_name=u"头像")
    message = models.TextField(verbose_name=u"评论")
    user = models.CharField(max_length=15, verbose_name=u"用户")
    class Meta:
        table_name = 'comment'

class Reply(BaseModel):
    comment = models.ForeignKeyField(Comment, index=True)
    create_time = models.DateTimeField(formats='%Y-%m-%d %H:%M:%S', verbose_name=u"创建时间")
    img = models.CharField(max_length=50, verbose_name=u"头像")
    message = models.TextField(verbose_name=u"回复")
    replyuser = models.CharField(max_length=15, verbose_name=u"to")
    user = models.CharField(max_length=15, verbose_name=u"from")
    class Meta:
        table_name = 'reply'

class Todolist(BaseModel):
    status = models.CharField(max_length=5, verbose_name=u"状态")
    title = models.CharField(max_length=100, verbose_name=u"事件")
    class Meta:
        table_name = 'todolist'


# -*- coding: utf-8 -*-

import os
import time
import json
import redis
import hashlib
import markdown
import datetime

from models import *
from peewee import fn
from tornado.web import MissingArgumentError, RequestHandler

__all__ = ["LoginHandler","LogoutHandler","BlogHandler","ListHandler","TagListHandler",
    "NewBlogHandler","SystemHandler","MessageHandler","ImgUploadHandler","DownloadHandler",
    "CountViewHandler","SearchHandler","ErrorHandler","CommentHandler","TodoHandler",
    "VisitorHandler","TemplateHandler"]

# 缓存时间设置
SESSION_CACHE = 60 * 10
BLOG_DETAIL = 60 * 60 * 24
CATE_BLOG_LIST = 60 * 60 * 24
TAG_BLOG_LIST = 60 * 60 * 24
TIME_GROUP_CACHE = 60 * 60 * 24
TIME_GROUP_LIST = 60 * 60 * 24
CATE_TAG_CACHE = 60 * 60 * 24 * 7
NEW_BLOG_LIST = 60 * 60 * 24
SEARCH_TITLE = 60 * 10

# redis
redis_cli = redis.StrictRedis()

class JsonDateTime(json.JSONEncoder):
    '''
    使json序列化支持时间转换
    '''
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(obj, datetime.date):
            return obj.strftime('%Y-%m-%d')
        return super().default(obj)


def CheckPermission(level):
    def wrapper(func):
        async def _check(self, *args, **kwargs):
            if self.current_user:
                permiss_list = self.current_user.get("permission")
                if level in permiss_list or self.current_user["user"] == "admin":
                    return await func(self, *args, **kwargs)
                else:
                    return self.write(status=9999, msg="权限不足")
            else:
                return self.write(status=1001, msg="请先登录")
        return _check
    return wrapper


class BaseHandler(RequestHandler):
    # 获取用户的 session
    def get_current_user(self):
        try:
            session_id = self.get_secure_cookie("session_id")
            if session_id:
                res = redis_cli.get(session_id)
                return json.loads(res.decode()) if res else None
        except Exception as err:
            raise err

    def write(self, chunk=None, status=0, msg=None, data=None, **kwargs):
        '''
        重写write方法,支持json序列化时间对象
        '''
        try:
            if chunk is None:
                chunk = {}
                chunk["status"] = status
                chunk["msg"] = msg
                chunk["data"] = data
                for k,v in kwargs.items():
                    chunk[k] = v

            if isinstance(chunk, dict):
                chunk = json.dumps(chunk, cls=JsonDateTime).replace("</", "<\\/")
                self.set_header("Content-Type", "application/json; charset=UTF-8")
            super(BaseHandler, self).write(chunk)
        finally:
            chunk = None


class LoginHandler(BaseHandler):
    '''
    登录
    '''
    def is_login(func):
        async def wrapper(self, *args, **kwargs):
            if self.current_user:
                return await func(self, *args, **kwargs)
            else:
                return self.write(status=1001, msg="请先登录")
        return wrapper

    @is_login
    async def get(self):
        try:
            flag = self.get_argument('time', '')
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")
        if flag:
            now = int(time.time())
            with open('admin.txt', 'r') as f:
                ts = f.read()
            return self.write(ts=int(ts), now=now)
        else:
            return self.write(msg="已经登录")

    async def post(self):
        '''
        登录
        :user   用户名
        :pwd    密码
        '''
        try:
            body = json.loads(self.request.body.decode())
            user = body.get('username')
            pwd = body.get('password')
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")

        if user == 'admin':
            now = str(int(time.time()))
            with open('admin.txt', 'w') as f:
                f.write(now)
        res = await Objects.execute(Author.select(Author.name, Author.img, Author.group).where(Author.name==user, Author.passwd==pwd))
        if res:
            res = res[0]
            data = {"user": res.name, "img": res.img, "permission": json.loads(res.group.permiss_list)}
            # 缓存
            session_id = hashlib.sha1((user+pwd).encode(encoding='utf-8')).hexdigest()
            redis_cli.setex(session_id, SESSION_CACHE, json.dumps(data))
            self.set_secure_cookie("session_id", session_id)
            self.write(msg="登录成功")
        else:
            self.write(status=1, msg="账号或密码错误")

    async def put(self):
        '''
        注册用户
        '''
        try:
            user = self.get_body_argument('user')
            pwd = self.get_body_argument('passwd')
            pwd2 = self.get_body_argument('passwd2')
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")

        if pwd != pwd2:
            self.write(status=1, msg="密码前后不同")
        else:
            res = await Objects.get_or_create(Author, name=user, passwd=pwd, img="/static/img/img.jpg", group=3)
            if res[1]:
                self.write(msg="注册成功")
            else:
                self.write(status=1, msg="用户已存在")


class LogoutHandler(BaseHandler):
    '''
    登出
    '''
    async def get(self):
        session_id = self.get_secure_cookie('session_id').decode()
        redis_cli.delete(session_id)
        self.write(msg="退出成功")


class BlogHandler(BaseHandler):

    def blogcache(func):
        async def wrapper(self, *args, **kwargs):
            try:
                Id = self.get_argument("id")
                jsons = self.get_argument("json", '')
            except MissingArgumentError as err:
                return self.write(status=1, msg="参数错误")
            if not jsons:
                key = "BlogHandler:" + str(Id)
            else:
                key = "BlogHandler:" + str(Id) + ":json"
            res = redis_cli.get(key)
            if res:
                self.set_header("X-Cache","HIT")
                return self.write(chunk=res)
            else:
                self.set_header("X-Cache","MISS")
                await func(self, *args, **kwargs)
        return wrapper

    @blogcache
    async def get(self):
        '''
        Id: 博文id
        jsons： 没有返回html，有返回原文
        '''
        try:
            Id = self.get_argument("id")
            jsons = self.get_argument("json", '')
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")

        key = "BlogHandler:" + str(Id)
        res = await Objects.get(Blog.select().where(Blog.id==Id))
        if res:
            lists = ["id", "title", "weight", "create_time", "change_time", "views", "digested", "keywords", "category", "author"]
            result = dict((i, getattr(res, i).name if isinstance(getattr(res, i), BaseModel) else getattr(res, i)) for i in lists)
            if not jsons:
                result["html"] = res.html
            else:
                key = key + ":json"
                result["body"] = res.body
            result["taglist"] = [i.tag.name for i in res.blogtag_set.select()]
            self.write(data=result)
            redis_cli.setex(key, BLOG_DETAIL, b"".join(self._write_buffer))
        else:
            self.write(status=1, msg="没有找到信息")

    @CheckPermission(1)
    async def put(self):
        '''
        博文修改
        :flag   修改类型
        :title  标题
        :category 分类
        :weight   权重
        :blogid   博文id
        '''
        try:
            flag = self.get_argument('flag')
            Rbody = json.loads(self.request.body.decode())
            blogid = Rbody.get('id')
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")

        key = "BlogHandler:" + str(blogid)
        keys = key + ":json"
        if flag == 'body':
            try:
                blogtext = Rbody.get('body')
                digested = Rbody.get('digested')
            except MissingArgumentError as err:
                return self.write(status=1, msg="参数错误")
            bloghtml = markdown.markdown(blogtext, extensions=['markdown.extensions.extra','markdown.extensions.toc','markdown.extensions.codehilite'])
            res = await Objects.execute(Blog.update(body=blogtext, digested=digested, html=bloghtml).where(Blog.id==blogid))
            if res:
                Rkeys = redis_cli.keys("ListHandler*")
                redis_cli.delect(key, keys, "NewBlogHandler", *Rkeys)
                self.write(msg="修改成功")
            else:
                self.write(status=1, msg="修改失败")
        elif flag == 'head':
            try:
                title = Rbody.get('title')
                category = Rbody.get('category')
                weight = Rbody.get('weight')
            except MissingArgumentError as err:
                return self.write(status=1, msg="参数错误")
            cate = await Objects.get(Category.select().where(Category.name == category))
            res = await Objects.get(Blog.select(Blog.title, Blog.category, Blog.weight).where(Blog.id == blogid))
            if cate:
                res = await Objects.execute(Blog.update(title=title, weight=weight, category=cate).where(Blog.id==blogid))
                if res:
                    Rkeys = redis_cli.keys("ListHandler*")
                    redis_cli.delect(key, keys, "NewBlogHandler", *Rkeys)
                    self.write(msg="修改成功")
                else:
                    self.write(status=1, msg="保存失败")
            else:
                self.write(status=1, msg="分类不存在")
        else:
            self.write(status=1, msg="传参错误")

    @CheckPermission(2)
    async def post(self):
        '''
        新建博文
        '''
        try:
            author = self.current_user['user']
            Rbody = json.loads(self.request.body.decode())
            create_time = Rbody.get('create_time')
            category = Rbody.get('category')
            body = Rbody.get('body')
            title = Rbody.get('title')
            digested = Rbody.get('digested')
            weight = Rbody.get('weight')
            taglist = Rbody.get('taglist')
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")

        html = markdown.markdown(body, extensions=['markdown.extensions.extra','markdown.extensions.toc','markdown.extensions.codehilite'])
        cate = await Objects.get(Category.select().where(Category.name==category))
        auth = await Objects.get(Author.select().where(Author.name==author))
        if cate and author:
            res = await Objects.create(Blog, title=title, body=body, html=html, digested=digested, author=auth, category=cate, weight=weight, create_time=create_time)
            if res:
                for tag in taglist:
                    tagres = await Objects.get(Tag.select().where(Tag.name == tag))
                    if tagres:
                        await Objects.create(Blogtag, blog=res, tag=tagres)
                    else:
                        await Objects.execute(Blogtag.delete().where(Blogtag.blog == res))
                        await Objects.delete(res)
                        return self.write(status=1, msg="标签不存在，保存失败")
                else:
                    Rkeys = redis_cli.keys("ListHandler*")
                    redis_cli.delete("NewBlogHandler", *Rkeys)
                    self.write(msg="创建成功")
            else:
                self.write(status=1, msg="博文创建失败")
        else:
            self.write(status=1, msg="作者或标签不存在，博文创建失败")

    @CheckPermission(3)
    async def delete(self):
        '''
        博文删除
        :blogid  博文id/单点删除
        :listid  博文id列表/批量删除
        '''
        try:
            blogid = self.get_argument('id')
        except MissingArgumentError as err:
            try:
                listid = self.get_argument('ids')
            except MissingArgumentError as err:
                return self.write(status=1, msg="参数错误")
            blogid = None

        if blogid is not None:
            key = "BlogHandler:" + str(blogid)
            keys = key + ":json"
            try:
                await Objects.execute(Blog.delete().where(Blog.id == blogid))
                await Objects.execute(Blogtag.delete().where(Blogtag.blog == blogid))
            except Exception as err:
                self.write(status=1, msg="删除失败")
            else:
                Rkeys = redis_cli.keys("ListHandler*")
                redis_cli.delete(key, keys, "NewBlogHandler", *Rkeys)
                self.write(msg="删除成功")
        else:
            listid = json.loads(listid)
            for blogid in listid:
                try:
                    await Objects.execute(Blog.delete().where(Blog.id == blogid))
                    await Objects.execute(Blogtag.delete().where(Blogtag.blog == blogid))
                except Exception as err:
                    break
                else:
                    key = "BlogHandler:" + str(blogid)
                    keys = key + ":json"
                    redis_cli.delete(key, keys)
            else:
                Rkeys = redis_cli.keys("ListHandler*")
                redis_cli.delete("NewBlogHandler", *Rkeys)
                return self.write(msg="删除成功")
            self.write(msg="部分删除成功")


class ListHandler(BaseHandler):

    def memorize(func):
        async def wrapper(self, *args, **kwargs):
            try:
                flag = self.get_argument('flag', '')
                search = self.get_argument('search', '')
                page = self.get_argument('page', 1)
                size = self.get_argument('limit', 5)
            except MissingArgumentError as err:
                return self.write(status=1, msg="参数错误")
            key = "ListHandler:%s:%s:%s:%s"%(flag,search,page,size)
            res = redis_cli.get(key)
            if res:
                self.set_header("X-Cache","HIT")
                self.write(chunk=res)
            else:
                self.set_header("X-Cache","MISS")
                await func(self, *args, **kwargs)
        return wrapper

    @memorize
    async def get(self):
        '''
        博文获取
        ;search 博文属性
        ;flag   搜索值
        ;page   页数
        ;limit  大小
        '''
        try:
            flag = self.get_argument('flag', '')
            search = self.get_argument('search', '')
            page = self.get_argument('page', 1)
            size = self.get_argument('limit', 5)
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")

        key = "ListHandler:%s:%s:%s:%s"%(flag,search,page,size)
        if search == 'category' and flag:
            if flag != '1':
                # 搜索
                totalnum = await Objects.count(Blog.select().where(Blog.category == flag).order_by(Blog.create_time.desc()))
                res = await Objects.execute(Blog.select(Blog.id, Blog.title, Blog.weight, Blog.author, Blog.category, Blog.create_time, Blog.change_time, Blog.views, Blog.digested).where(Blog.category == flag).order_by(Blog.create_time.desc()).paginate(int(page), int(size)))
            elif flag == '1':
                totalnum = await Objects.count(Blog.select().order_by(Blog.create_time.desc()))
                res = await Objects.execute(Blog.select(Blog.id, Blog.title, Blog.weight, Blog.author, Blog.category, Blog.create_time, Blog.change_time, Blog.views, Blog.digested).order_by(Blog.create_time.desc()).paginate(int(page), int(size)))

            if res:
                result = []
                lists = ["id", "title", "weight", "author", "category", "create_time", "change_time", "views", "digested"]
                for resu in res:
                    resul = dict((i, getattr(resu, i).name if isinstance(getattr(resu, i), BaseModel) else getattr(resu, i)) for i in lists)
                    result.append(resul)
                self.write(data=result, total=totalnum)
                redis_cli.setex(key, CATE_BLOG_LIST, b"".join(self._write_buffer))
            else:
                self.write(status=1, msg="数据为空")

        elif search == 'tag' and flag:
            res = await Objects.execute(Blogtag.select().where(Blogtag.tag == flag))
            totalnum = len(res)
            if res:
                result = []
                lists = ["id", "title", "weight", "author", "category", "create_time", "change_time", "views", "digested"]
                for resu in res:
                    resu = resu.blog
                    resul = dict((i, getattr(resu, i).name if isinstance(getattr(resu, i), BaseModel) else getattr(resu, i)) for i in lists)
                    result.append(resul)
                self.write(data=result, total=totalnum)
                redis_cli.setex(key, TAG_BLOG_LIST, b"".join(self._write_buffer))
            else:
                self.write(status=1, msg="标签分类失败")

        elif search == 'group' and flag:
            if flag == '1':
                res = await Objects.execute(Blog.select(fn.Count(Blog.id).alias("nums"), Blog.create_time).group_by(Blog.create_time.month))
                if res:
                    result = []
                    for resu in res:
                        resul = {}
                        resul['nums'] = resu.nums
                        resul['flag'] = str(resu.create_time.year) + '年' + str(resu.create_time.month) + '月'
                        resul['time'] = resu.create_time.strftime("%Y-%m")
                        result.append(resul)
                    self.write(data=result)
                    redis_cli.setex(key, TIME_GROUP_CACHE, b"".join(self._write_buffer))
                else:
                    self.write(status=1, msg="时间分组失败")
            else:
                totalnum = await Objects.count(Blog.select().where(Blog.create_time.startswith(flag)))
                res = await Objects.execute(Blog.select().where(Blog.create_time.startswith(flag)).paginate(int(page), int(size)))
                if res:
                    result = []
                    lists = ["id", "title", "weight", "author", "category", "create_time", "change_time", "views", "digested"]
                    for resu in res:
                        resul = dict((i, getattr(resu, i).name if isinstance(getattr(resu, i), BaseModel) else getattr(resu, i)) for i in lists)
                        result.append(resul)
                    self.write(data=result, total=totalnum)
                    redis_cli.setex(key, TIME_GROUP_LIST, b"".join(self._write_buffer))
                else:
                    self.write(status=1, msg="数据为空")
        else:
            self.write(status=1, msg="未识别的请求")


class TagListHandler(BaseHandler):

    def tagscache(func):
        async def warpper(self, *args, **kwargs):
            res = redis_cli.get("TagListHandler")
            if res:
                self.set_header("X-Cache","HIT")
                self.write(chunk=res)
            else:
                self.set_header("X-Cache","MISS")
                await func(self, *args, **kwargs)  
        return warpper

    #返回标签/分类列表
    @tagscache
    async def get(self):
        lists = {}

        res = await Objects.execute(Tag.select(Tag.name, Tag.id))
        if res:
            result = []
            for resu in res:
                resul = dict((i, getattr(resu, i)) for i in ["id", "name"])
                result.append(resul)
        lists['tag'] = result

        res = await Objects.execute(Category.select(Category.id, Category.name))
        if res:
            result = []
            for resu in res:
                resul = dict((i, getattr(resu, i)) for i in ["id", "name"])
                result.append(resul)
        lists['category'] = result
        self.write(data=lists)
        redis_cli.setex("TagListHandler", CATE_TAG_CACHE, b"".join(self._write_buffer))


class NewBlogHandler(BaseHandler):
    '''
    最新博文
    '''
    def newblogcache(func):
        async def wrapper(self, *args, **kwargs):
            res = redis_cli.get("NewBlogHandler")
            if res:
                self.set_header("X-Cache","HIT")
                self.write(chunk=res)
            else:
                self.set_header("X-Cache","MISS")
                await func(self, *args, **kwargs)
        return wrapper

    @newblogcache
    async def get(self):
        res = await Objects.execute(Blog.select(Blog.id, Blog.title).order_by(Blog.create_time.desc()).limit(5))
        if res:
            result = []
            for resu in res:
                resul = dict((i, getattr(resu, i)) for i in ["id", "title"])
                result.append(resul)
            self.write(data=result)
            redis_cli.setex("NewBlogHandler", NEW_BLOG_LIST, b"".join(self._write_buffer))
        else:
            self.write(status=1, msg="没有文章")


class SystemHandler(BaseHandler):
    @CheckPermission(4)
    async def get(self):
        sort = self.get_argument('sort', 'true')
        limits = self.get_argument('limit', 60)
        limits = int(limits)

        res = await Objects.execute(Skynet.select().order_by(Skynet.create_time.desc()).limit(limits))
        #lists = [(["min1", "min5", "min15"], "load"), (["uscpu", "sycpu"], "cpu"), (["total", "used", "free"], "memory"), (["netin", "netout"], "net")]
        if res:
            r_data = {}
            function = lambda x: [x.min1,x.min5,x.min15,x.uscpu,x.sycpu,x.total,x.used,x.free,x.netin,-x.netout,x.create_time.strftime("%H:%M")]
            min1,min5,min15,uscpu,sycpu,total,used,free,netin,netout,create_time = zip(*map(function,res))
            r_data['load'] = {'min1':min1, 'min5':min5, 'min15':min15}
            r_data['cpu'] = {'uscpu':uscpu, 'sycpu':sycpu}
            r_data['memory'] = {'total':total, 'used':used, 'free':free}
            r_data['net'] = {'netin':netin, 'netout':netout}
            r_data['create_time'] = create_time
            self.write(data=r_data)
        else:
            self.write(status=1, msg="未知错误")


class MessageHandler(BaseHandler):
    '''
    系统通知
    '''
    @CheckPermission(5)
    async def get(self):
        try:
            limit = self.get_argument('limit', 5)
            page = self.get_argument('page', 1)
            total = self.get_argument('total', 0)
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")
        res = await Objects.execute(Message.select())
        if res:
            result = []
            for resu in res:
                resul = dict((i, getattr(resu, i)) for i in ["id", "content", "status", "create_time"])
                result.append(resul)
            self.write(data=result)
        else:
            self.write(status=1, msg="没有消息", data=result)
    @CheckPermission(6)
    async def post(self):
        try:
            msgid = self.get_argument('msgid')
            status = self.get_argument('status')
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")
        res = await Objects.execute(Message.update(status=status).where(Message.id==msgid))
        if res:
            res = await Objects.execute(Message.select())
            result = []
            for resu in res:
                resul = dict((i, getattr(resu, i)) for i in ["id", "content", "status", "create_time"])
                result.append(resul)
            self.write(msg="操作成功",data=result)
        else:
            self.write(status=1, msg="操作失败")


class ImgUploadHandler(BaseHandler):
    @CheckPermission(7)
    async def post(self):
        '''
        图片上传
        '''
        #upload_path = os.path.join(os.path.dirname(__file__), 'upload')
        upload_path = "/home/niukaixin/www/html/static/img/"
        files = self.request.files.get('file', None)
        if not files:
            return self.write(status=1, msg="没有接收到文件")
        for file in files:
            filename = file['filename']
            filepath = os.path.join(upload_path, filename)
            with open(filepath, 'wb') as f:
                f.write(file['body'])
        self.write(data="http://www.52pyc.cn/static/img/"+filename)
    @CheckPermission(8)
    async def delete(self):
        '''
        图片删除
        '''
        #upload_path = os.path.join(os.path.dirname(__file__), 'upload')
        upload_path = "/home/niukaixin/www/html/static/img/"
        filename = self.get_argument('name', '')
        if not filename:
            return self.write(status=1, msg="没有参数")
        filepath = os.path.join(upload_path, filename)
        try:
            if os.path.isfile(filepath):
                os.remove(filepath)
            else:
                return self.write(msg="图片不存在")
        except:
            return self.write(msg="删除失败")
        self.write(msg="删除图片成功")


class DownloadHandler(BaseHandler):
    @CheckPermission(9)
    async def get(self):
        try:
            blogid = self.get_argument('id')
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")
        res = await Objects.get(Blog.select(Blog.title, Blog.body).where(Blog.id == blogid))
        if res:
            self.set_header('Content-Type', 'application/octet-stream')
            Disposition = 'attachment; filename=%s%s'%(res.title,'.md')
            self.set_header('Content-Disposition', Disposition)
            self.write(str(res.body))
        else:
            self.write(status=1, msg="下载失败")


class CountViewHandler(BaseHandler):
    '''
    访问统计
    '''
    async def get(self):
        r_data = {}
        with open('admin.txt', 'r') as f:
            ls = f.read()
        time = datetime.datetime.utcfromtimestamp(int(ls)).__str__()[:10]
        r_data['time'] = time
        r_data['blogsums'] = await Objects.count(Blog.select(Blog.id))
        r_data['message'] = await Objects.count(Message.select(Message.id))
        answer = await Objects.get(Visitor.select(Visitor.sums).where(Visitor.id==1))
        r_data['views'] = answer.sums if answer else 0
        self.write(data=r_data)

    async def post(self):
        try:
            index = self.get_argument('index')
        except MissingArgumentError as err:
            try:
                blogid = self.get_argument('id')
            except MissingArgumentError as err:
                return self.write(status=1, msg="参数错误")
            index = None
        if index is not None:
            now = datetime.date.today()
            res = await Objects.execute(Visitor.update(sums=Visitor.sums+1).where(Visitor.time == now))
            if not res:
                await Objects.create(Visitor, time=now, sums=1)
            autosum = await Objects.execute(Visitor.update(sums=Visitor.sums + 1).where(Visitor.id == 1))
            self.write()
        else:
            res = await Objects.execute(Blog.update(views=Blog.views+1).where(Blog.id==blogid))
            if res:
                self.write()
            else:
                self.write(status=1, msg="文章不存在")


class SearchHandler(BaseHandler):

    def searchtitle(func):
        async def warpper(self, *args, **kwargs):
            try:
                value = self.get_argument('title')
            except MissingArgumentError as err:
                return self.write(status=1, msg="参数错误")
            key = "Search:" + str(value)
            res = redis_cli.get(key)
            if res:
                self.set_header("X-Cache","HIT")
                self.write(chunk=res)
            else:
                self.set_header("X-Cache","MISS")
                await func(self, *args, **kwargs)  
        return warpper

    @searchtitle
    async def get(self):
        try:
            value = self.get_argument('title')
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")

        res = await Objects.execute(Blog.select(Blog.id, Blog.title.alias("value")).where(Blog.title.contains(value)))
        if res:
            result = []
            for resu in res:
                resul = dict((i, getattr(resu, i)) for i in ["id", "value"])
                result.append(resul)
            key = "Search:" + str(value)
            self.write(data=result)
            redis_cli.setex(key, SEARCH_TITLE, b"".join(self._write_buffer))
        else:
            self.write(msg="查询为空")

    @CheckPermission(10)
    async def put(self):
        '''
        :page   页数
        :size   页面大小
        :select 筛选条件
        :value  筛选内容
        '''
        try:
            page = self.get_argument('page', 1)
            size = self.get_argument('limit', 5)
            select = self.get_argument("select")
            value = self.get_argument("value")
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")

        autores = Blog.select(Blog.id, Blog.title, Blog.weight, Blog.author, Blog.category, Blog.create_time, Blog.change_time, Blog.views, Blog.digested)
        dicts = {"author":Author, "category":Category, "title": Blog.title, "digested": Blog.digested}
        dicts2 = {'views': Blog.views, 'weight': Blog.weight}
        if select in dicts and value:
            if select in ["author", "category"]:
                totalnum = await Objects.count(Blog.select(Blog.id).join(dicts[select]).where(dicts[select].name.contains(value)))
                res = await Objects.execute(autores.join(dicts[select]).where(dicts[select].name.contains(value)).paginate(int(page), int(size)))
            else:
                totalnum = await Objects.count(Blog.select(Blog.id).where(dicts[select].contains(value)))
                res = await Objects.execute(autores.where(dicts[select].contains(value)).paginate(int(page), int(size)))
        elif select in dicts2 and value:
            if value[0] == '@':
                value = value[1:]
                totalnum = await Objects.count(Blog.select(Blog.id).where(dicts2[select] < value))
                res = await Objects.execute(autores.where(dicts2[select] < value).paginate(int(page), int(size)))
            elif value[-1] == '$':
                value = value[:-1]
                totalnum = await Objects.count(Blog.select(Blog.id).where(dicts2[select] > value))
                res = await Objects.execute(autores.where(dicts2[select] > value).paginate(int(page), int(size)))
            else:
                totalnum = await Objects.count(Blog.select(Blog.id).where(dicts2[select] == value))
                res = await Objects.execute(autores.where(dicts2[select] == value).paginate(int(page), int(size)))
        else:
            return self.write(status=1, msg="未识别的请求")

        if res:
            result = []
            lists = ["id", "title", "weight", "author", "category", "create_time", "change_time", "views", "digested"]
            for resu in res:
                resul = dict((i, getattr(resu, i).name if isinstance(getattr(resu, i), BaseModel) else getattr(resu, i)) for i in lists)
                result.append(resul)
            self.write(data=result, total=totalnum)
        else:
            self.write(status=1, msg="数据为空", total=totalnum)


class ErrorHandler(BaseHandler):
    def get(self):
        self.send_error(404)

    def write_error(self, status_code, **kwargs):
        self.render('404.html')


class CommentHandler(BaseHandler):
    '''
    评论
    '''
    async def get(self):
        try:
            blogid = self.get_argument('id')
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")

        res = await Objects.execute(Comment.select().where(Comment.blog == blogid).order_by(Comment.floor.desc()))
        res = self._time(res)
        result = []
        for resu in res:
            resul = dict((i, getattr(resu, i)) for i in ["id", "img", "user", "message", "create_time", "floor"])
            resul["show"] = False
            resul["look"] = "查看"
            chils = await Objects.execute(Reply.select().where(Reply.comment == resu.id))
            chils = self._time(chils)
            childr = []
            for chil in chils:
                child = dict((i, getattr(chil, i)) for i in ["id", "img", "user", "message", "create_time"])
                childr.append(child)
            resul['children'] = childr
            result.append(resul)
        self.write(data=result)

    def _time(self, objs):
        now = datetime.datetime.now()
        for obj in objs:
            time = (now - obj.create_time).seconds
            if time//60 == 0:
                obj.create_time = '%s秒前'%(time)
            elif time//3600 == 0:
                obj.create_time = '%s分钟前'%(time//60)
            elif time//86400 == 0:
                obj.create_time = '%s小时前'%(time//3600)
            else:
                obj.create_time = '%s天前'%(time//86400)
        return objs

    @CheckPermission(11)
    async def post(self):
        try:
            user = self.current_user.get("user")
            img = self.current_user.get("img")
            blogid = self.get_body_argument("blogid")
            status = self.get_body_argument("status")
            message = self.get_body_argument("message")
            replyid = self.get_body_argument("replyid")
            replyuser = self.get_body_argument("replyuser")
        except MissingArgumentError as err:
            return self(status=1, msg="参数错误")

        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            if message.split('\n')[0].split('@')[1]:
                replyblog = False
                message = '\n'.join(message.split('\n')[1:])
        except:
            replyblog = True
        if status == 0 or replyblog:
            res = await Objects.get(Comment.select(fn.Max(Comment.floor).alias("sum")).where(Comment.blog == blogid))
            if res:
                if res.sum:
                    floor = res.sum + 1
                else:
                    floor = 1
            res = await Objects.create(Comment, user=user, message=message, create_time=now, floor=floor, blog_id=blogid, img=img)
            if res:
                return self.write(msg="回复成功")
            else:
                self.write(status=1, msg="回复失败")
        elif status >= 1 and not replyblog:
            res = await Objects.create(Reply, user=user, message=message, create_time=now, comment_id=replyid, img=img, replyuser=replyuser)
            if res:
                return self.write(msg="回复成功")
            else:
                return self.write(status=1, msg="回复失败")


class TodoHandler(BaseHandler):
    '''
    待做事件
    '''
    @CheckPermission(12)
    async def get(self):
        res = await Objects.execute(Todolist.select())
        result = []
        for resu in res:
            resul = dict((i, getattr(resu, i)) for i in ["id", "title", "status"])
            if resul['status'] == 'false':
                resul['status'] = False
            else:
                resul['status'] = True
            result.append(resul)
        self.write(data=result)

    @CheckPermission(13)
    async def put(self):
        try:
            body = json.loads(self.request.body.decode())
            todoid = body['id']
            title = body['title']
            status = body['status']
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")
        status = 'true' if status else 'false'
        res = await Objects.execute(Todolist.update(title=title, status=status).where(Todolist.id == todoid))
        if res:
            self.write(msg="修改成功")
        else:
            self.write(status=1, msg="修改失败")

    @CheckPermission(14)
    async def post(self):
        print(self)
        try:
            title = json.loads(self.request.body.decode()).get("title")
        except MissingArgumentError as err:
            return self.write(status=1, msg="参数错误")
        res = await Objects.get_or_create(Todolist, title=title, status="false")
        if res[1]:
            self.write(msg="创建成功")
        else:
            self.write(status=1, msg="事件已存在")

    @CheckPermission(15)
    async def delete(self):
        body = json.loads(self.request.body.decode())
        res = await Objects.execute(Todolist.delete().where(Todolist.id == body))
        if res:
            self.write(msg="删除成功")
        else:
            self.write(status=1, msg="删除失败")


class VisitorHandler(BaseHandler):
    @CheckPermission(16)
    async def get(self):
        import copy
        res = await Objects.execute(Visitor.select(Visitor.time.alias("name"), Visitor.sums.alias("value")).order_by(Visitor.time.desc()).limit(7))
        result = []
        for resu in res:
            resul = dict((i, getattr(resu, i)) for i in ["name", "value"])
            result.append(resul)
        result.reverse()
        result2 = copy.deepcopy(result)
        for item,result1 in enumerate(result2):
            if item != 0:
                result1['value'] += result2[item-1]['value']
        self.write(data=result, data2=result2)


class TemplateHandler(RequestHandler):
    async def get(self, ids):
        res = await Objects.get(Blog.select(Blog.title, Blog.keywords, Blog.digested).where(Blog.id==ids))
        if res:
            title = res.title
            title += " | 小牛运维站"
            keywords = res.keywords
            description = res.digested
        else:
            title = "小牛运维站"
            keywords = "python,小牛,django,tornado,线程,asyncio,async/await,协程,异步,多线程"
            description = ""
        heads = {
            "title": title,
            "keywords": keywords,
            "description": description,
        }
        self.render("detail.html", **heads)

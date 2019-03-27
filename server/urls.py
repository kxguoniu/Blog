# -*- coding: utf-8 -*-

import tornado.web
from tornado.log import access_log
from views import *

def Custom(handler):
    if handler.get_status() < 400:
        log_method = access_log.info
    elif handler.get_status() < 500:
        log_method = access_log.warning
    else:
        log_method = access_log.error
    request_time = 1000.0 * handler.request.request_time()
    if "X-Real-Ip" in handler.request.headers.keys():
        real_ip = handler.request.headers["X-Real-Ip"]
    else:
        real_ip = "127.0.0.1"
    log_method("%s %d %s %s %s %.2fms", real_ip, handler.get_status(),
                   handler.request.version, handler.request.method, handler.request.uri, request_time)

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r'/newblog', NewBlogHandler),      #最新博文
            (r'/blog', BlogHandler),            #博文增删改查
            (r'/bloglist', ListHandler),        #博文列表
            (r'/taglist', TagListHandler),      #标签/分类 列表
            (r'/login', LoginHandler),          #登录
            (r'/logout', LogoutHandler),        #登出
            (r'/system', SystemHandler),        #系统监控
            (r'/message', MessageHandler),      #系统通知
            (r'/imgupload', ImgUploadHandler),  #图片上传
            (r'/download', DownloadHandler),    #博文下载
            (r'/countview', CountViewHandler),         #访问计数
            (r'/search', SearchHandler),        #搜索
            (r'/comment', CommentHandler),      #评论
            (r'/todolist', TodoHandler),        #待办事项
            (r'/visitor', VisitorHandler),      #七天访问量
            (r'/blogdetail/(?P<ids>\d*)', TemplateHandler), # 模板
            (r'.*', ErrorHandler),              #捕捉错误页面
        ]
        settings = dict(
            log_function=Custom,
            debug=True,     #调试模式
            cookie_secret="SECRET_DONT_LEAK",
            login_url="/login",
            #xsrf_cookies=True,
        )
        super(Application, self).__init__(handlers, **settings)
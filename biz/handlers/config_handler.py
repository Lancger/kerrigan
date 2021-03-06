#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Contact : 191715030@qq.com
Author  : shenshuo
Date    : 2019/1/21
Desc    : api
"""
import json
from libs.base_handler import BaseHandler
from models.models import KerriganProject, KerriganConfig, KerriganHistory, KerriganPublish, model_to_dict
from sqlalchemy import or_
from websdk.db_context import DBContext


def check_contain_chinese(check_str):
    for ch in check_str:
        if u'\u4e00' <= ch <= u'\u9fff':
            return True
    return False


class ProjectHandler(BaseHandler):
    def get(self, *args, **kwargs):
        key = self.get_argument('key', default=None, strip=True)
        project_list = []
        with DBContext('r') as session:
            if key:
                project_info = session.query(KerriganProject).filter(
                    or_(KerriganProject.project_name.like('%{}%'.format(key)),
                        KerriganProject.project_code.like('%{}%'.format(key)))).all()
            else:
                project_info = session.query(KerriganProject).all()

        for msg in project_info:
            data_dict = model_to_dict(msg)
            data_dict['create_time'] = str(data_dict['create_time'])
            project_list.append(data_dict)

        self.write(dict(code=0, msg='获取成功', data=project_list))

    def post(self, *args, **kwargs):
        data = json.loads(self.request.body.decode("utf-8"))
        project_code = data.get('project_code')
        project_name = data.get('project_name')

        if not project_name or not project_name:
            return self.write(dict(code=-2, msg='关键参数不能为空'))

        if check_contain_chinese(project_code):
            return self.write(dict(code=-1, msg='项目代号或者英文名称不能有汉字'))

        nickname = self.get_current_nickname()
        with DBContext('w', None, True) as session:
            is_exist = session.query(KerriganProject.project_id).filter(
                KerriganConfig.project_code == project_code).first()
            if is_exist:
                return self.write(dict(code=-2, msg='名称不能重复'))

            session.add(KerriganProject(project_name=project_name, project_code=project_code, create_user=nickname))

        self.write(dict(code=0, msg='添加成功'))


class ProjectTreeHandler(BaseHandler):
    def get(self, *args, **kwargs):
        project_code = self.get_argument('project_code', default=None, strip=True)
        if not project_code:
            return self.write(dict(code=-1, msg='关键参数不能为空'))

        config_list = []
        with DBContext('r') as session:
            config_info = session.query(KerriganConfig).filter(KerriganConfig.project_code == project_code,
                                                               KerriganConfig.is_deleted == False).all()
            project_info = session.query(KerriganProject.project_name).filter(
                KerriganConfig.project_code == project_code).first()

            if not project_info:
                project_name = project_code
            else:
                project_name = project_info[0]

            for m in config_info:
                data_dict = model_to_dict(m)
                data_dict.pop('create_time')
                config_list.append(data_dict)

        _tree = [{"open": True, "name": project_code, "children": [],
                  "display_name": "%s | %s" % (project_code, project_name)}]

        if config_list:
            tmp_tree = {
                "environ": {},
                "service": {},
                "filename": {},
            }

            for t in config_list:
                filename, service, environ = t["filename"], t['service'], t["environment"]

                # 因为是第一层所以没有parent
                tmp_tree["environ"][environ] = {
                    "open": True, "name": environ, "parent": "root", "children": []
                }

                # 父节点是对应的environ
                tmp_tree["service"][environ + "|" + service] = {
                    "open": True, "name": service, "parent": environ,
                    "children": []
                }

                # 最后一层没有children
                tmp_tree["filename"][environ + "|" + service + "|" + filename] = {
                    "open": True, "id": t['id'],
                    "name": filename,
                    "parent": environ + "|" + service
                }

            for tmpFilename in tmp_tree["filename"].values():
                tmp_tree["service"][tmpFilename["parent"]]["children"].append(tmpFilename)

            # service的数据插入到environ的children中
            for tmpService in tmp_tree["service"].values():
                tmp_tree["environ"][tmpService["parent"]]["children"].append(tmpService)

            for tmpEnviron in tmp_tree["environ"].values():
                _tree[0]["children"].append(tmpEnviron)

            return self.write(dict(code=0, msg='成功', data=_tree))
        else:
            return self.write(dict(code=-1, msg='成功', data=_tree))


class ConfigurationHandler(BaseHandler):
    def get(self, *args, **kwargs):
        project_code = self.get_argument('project_code', default=None, strip=True)
        environment = self.get_argument('environment', default=None, strip=True)
        service = self.get_argument('service', default=None, strip=True)
        filename = self.get_argument('filename', default=None, strip=True)
        publish = self.get_argument('publish', default=None, strip=True)
        if not project_code or not environment or not service or not filename:
            return self.write(dict(code=-1, msg='关键参数不能为空'))

        with DBContext('r') as session:
            if publish:
                conf_info = session.query(KerriganConfig.content).filter(KerriganConfig.project_code == project_code,
                                                                         KerriganConfig.environment == environment,
                                                                         KerriganConfig.service == service,
                                                                         KerriganConfig.filename == filename,
                                                                         KerriganConfig.is_deleted == False,
                                                                         KerriganConfig.is_published == True).first()
            else:
                config_key = "/{}/{}/{}/{}".format(project_code, environment, service, filename)
                conf_info = session.query(KerriganPublish.content).filter(KerriganPublish.config == config_key).first()
        if not conf_info:
            return self.write(dict(code=-2, msg='没有数据', data=dict(content='')))

        self.write(dict(code=0, msg='获取成功', data=dict(content=conf_info[0])))

    ### 添加
    def post(self, *args, **kwargs):
        data = json.loads(self.request.body.decode("utf-8"))
        project_id = data.get('project_id')
        project_code = data.get('project_code')
        environment = data.get('environment')
        service = data.get('service')
        filename = data.get('filename')
        content = data.get('content')
        if not project_code or not environment or not service or not filename:
            return self.write(dict(code=-1, msg='关键参数不能为空'))

        with DBContext('r') as session:
            is_exist = session.query(KerriganConfig.id).filter(KerriganConfig.project_code == project_code,
                                                               KerriganConfig.environment == environment,
                                                               KerriganConfig.service == service,
                                                               KerriganConfig.filename == filename,
                                                               KerriganConfig.is_deleted == False).first()
        if is_exist:
            return self.write(dict(code=-1, msg='key重复了'))

        ### 防重复
        config_key = "/{}/{}/{}/{}".format(project_code, environment, service, filename)
        with DBContext('w', None, True) as session:
            session.query(KerriganConfig).filter(KerriganConfig.project_code == project_code,
                                                 KerriganConfig.environment == environment,
                                                 KerriganConfig.service == service, KerriganConfig.filename == filename
                                                 ).update({KerriganConfig.is_deleted: True})

            session.add(
                KerriganConfig(pid=project_id, project_code=project_code, environment=environment, service=service,
                               filename=filename, content=content, create_user=self.get_current_nickname()))

            ### 历史记录
            session.add(KerriganHistory(config=config_key, content=content, create_user=self.get_current_nickname()))

        self.write(dict(code=0, msg='添加成功'))

    ### 修改
    def put(self, *args, **kwargs):
        data = json.loads(self.request.body.decode("utf-8"))
        project_code = data.get('project_code')
        environment = data.get('environment')
        service = data.get('service')
        filename = data.get('filename')
        content = data.get('content')
        if not project_code or not environment or not service or not filename:
            return self.write(dict(code=-1, msg='关键参数不能为空'))

        with DBContext('w', None, True) as session:
            session.query(KerriganConfig).filter(KerriganConfig.project_code == project_code,
                                                 KerriganConfig.environment == environment,
                                                 KerriganConfig.service == service,
                                                 KerriganConfig.filename == filename,
                                                 KerriganConfig.is_deleted == False).update(
                {KerriganConfig.content: content, KerriganConfig.is_published: False,
                 KerriganConfig.create_user: self.get_current_nickname()})

        self.write(dict(code=0, msg='配置修改成功'))

    ### 删除
    def delete(self, *args, **kwargs):
        data = json.loads(self.request.body.decode("utf-8"))
        project_code = data.get('project_code')
        environment = data.get('environment')
        service = data.get('service')
        filename = data.get('filename')
        if not project_code or not environment or not service or not filename:
            return self.write(dict(code=-1, msg='关键参数不能为空'))

        with DBContext('w', None, True) as session:
            session.query(KerriganConfig).filter(KerriganConfig.project_code == project_code,
                                                 KerriganConfig.environment == environment,
                                                 KerriganConfig.service == service, KerriganConfig.filename == filename
                                                 ).update({KerriganConfig.is_deleted: True})

        return self.write(dict(code=0, msg='删除成功'))

    ### 发布
    def patch(self, *args, **kwargs):
        data = json.loads(self.request.body.decode("utf-8"))
        config_id = data.get('config_id')
        if not config_id:
            return self.write(dict(code=-1, msg='关键参数不能为空'))

        with DBContext('w', None, True) as session:
            session.query(KerriganConfig).update({KerriganConfig.is_published: True})
            config_info = session.query(KerriganConfig).filter(KerriganConfig.id == config_id).first()

            config_key = "/{}/{}/{}/{}".format(config_info.project_code, config_info.environment, config_info.service,
                                               config_info.filename)
            publish = session.query(KerriganPublish.id).filter(KerriganPublish.config == config_key).first()
            if not publish:
                session.add(KerriganPublish(config=config_key, content=config_info.content,
                                            create_user=self.get_current_nickname()))
            else:
                session.query(KerriganPublish).filter(KerriganPublish.config == config_key).update(
                    {KerriganPublish.content: config_info.content,
                     KerriganConfig.create_user: self.get_current_nickname()})

        return self.write(dict(code=0, msg='发布成功'))


class HistoryConfigHandler(BaseHandler):
    def get(self, *args, **kwargs):
        project_code = self.get_argument('project_code', default=None, strip=True)
        environment = self.get_argument('environment', default=None, strip=True)
        service = self.get_argument('service', default=None, strip=True)
        filename = self.get_argument('filename', default=None, strip=True)
        if not project_code or not environment or not service or not filename:
            return self.write(dict(code=-1, msg='关键参数不能为空'))

        history_list = []
        config_key = "/{}/{}/{}/{}".format(project_code, environment, service, filename)
        with DBContext('r') as session:
            conf_info = session.query(KerriganHistory.content).filter(KerriganConfig.config == config_key).all()

        for msg in conf_info:
            data_dict = model_to_dict(msg)
            data_dict['create_time'] = str(data_dict['create_time'])
            history_list.append(data_dict)
        return self.write(dict(code=0, msg='获取历史成功', data=history_list))

    ### 回滚
    def patch(self, *args, **kwargs):
        history_id = self.get_argument('history_id', default=None, strip=True)

        with DBContext('r') as session:
            conf_info = session.query(KerriganHistory).filter(KerriganConfig.id == history_id).all()

        with DBContext('w', None, True) as session:
            session.query(KerriganConfig).filter(KerriganConfig.project_code == conf_info.project_code,
                                                 KerriganConfig.environment == conf_info.environment,
                                                 KerriganConfig.service == conf_info.service,
                                                 KerriganConfig.filename == conf_info.filename,
                                                 KerriganConfig.is_deleted == False).update(
                {KerriganConfig.content: conf_info.content, KerriganConfig.is_published: False,
                 KerriganConfig.create_user: self.get_current_nickname()})


config_urls = [
    (r"/v1/conf/project/", ProjectHandler),
    (r"/v1/conf/config/", ConfigurationHandler),
    (r"/v1/conf/tree/", ProjectTreeHandler),
    (r"/v1/conf/history/", HistoryConfigHandler)
]
if __name__ == "__main__":
    pass

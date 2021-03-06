from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from .db import get_db,get_db_by_config
from .auth import login_required
from datetime import datetime
from blinker import signal
import json
import _thread

records_updated_signal = signal("update records")#警示记录发生更新的信号

def produce_record(db, criminal_id, user_id, camera_id, interval):
    '''
    生成一条警示记录
    :param db: 传入的数据库
    :param criminal_id: 罪犯id
    :param user_id: 摄像头所属用户id
    :param camera_id: 相机id
    :param interval: 生成记录之间的最少间隔（单位：min）
    :return:
    '''
    last_time = db.execute(
        'SELECT time FROM history_records WHERE criminal_id = ? AND user_id = ? AND camera_id = ? ORDER BY time DESC',
        (criminal_id, user_id, camera_id)
    ).fetchone() #查询最近一条记录（除了时间之外其他字段都相同）

    current_time = datetime.now() #获取当前时间
    if last_time is None or \
            ((current_time - datetime.strptime(last_time['time'], "%Y-%m-%d %H:%M:%S")).seconds >= 60 * float(interval)):
        # 如果最近不存在该嫌犯的记录
        db.execute(
            'INSERT INTO history_records(criminal_id, time, user_id, camera_id)'
            'VALUES (?, ?, ?, ?)',
            (criminal_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, camera_id)
        )
        db.commit()
        records_updated_signal.send(user_id)#发送信号，表示用户usre_id的警示记录发生了更新


def get_history_records(db, user_id):
    '''获取用户user_id的所有历史记录'''
    records = db.execute(
        'SELECT r.id, u.username as username, c.name as criminal_name, '
        'c.id as criminal_id, c.important as criminal_important, r.time,'
        'r.camera_id FROM user u, criminal c, history_records r '
        'WHERE r.criminal_id = c.id and r.user_id = u.id and u.id = ?'
        'ORDER BY r.time DESC ',
        (user_id,)
    )
    return records

def _create_json_response(records):
    '''将records进行json序列化'''
    new_records = []
    for record in records:
        new_record={
            'criminal_name':record['criminal_name'],
            'criminal_id':record['criminal_id'],
            'time': record['time'],
            'camera_id': record['camera_id'],
            'criminal_important': record['criminal_important'],
            'id': record['id'],
        }
        new_records.append(new_record)
    return json.dumps(new_records)


class RecordsGenerator:
    '''历史记录生成器'''
    def __init__(self, user_id, db_config):
        self.user_id = user_id
        self.db_config = db_config
        records_updated_signal.connect(self.on_records_update)
        self.lock = _thread.allocate_lock()

    def on_records_update(self, user_id):
        '''当历史警示记录更新时'''
        if user_id == self.user_id:
            if self.lock.locked():
                self.lock.release()

    def __iter__(self):
        while True:
            self.lock.acquire()  #只有当历史警示记录发生更新时，才会向客户端推送消息
            db = get_db_by_config(config=self.db_config)
            records = get_history_records(db, self.user_id).fetchmany(5)
            records = _create_json_response(records)
            yield "data: " + records + "\n\n"

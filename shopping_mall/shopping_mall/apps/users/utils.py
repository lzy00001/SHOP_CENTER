import re

from django.contrib.auth.backends import ModelBackend

from users.models import User


def jwt_response_payload_handler(token, user=None, response=None):
    """自定义jwt认证成功返回数据"""
    return {
        "token":token,
        "user_id":user.id,
        "username":user.username,
    }


def get_user_by_count(username):
    """
    根据账号获取user对象
    :param username: 账号：手机号或用户名
    :return: user对象或者None
    """
    try:
        if re.match(r'^1[3-9]\d{9}$', username):
            user = User.objects.get(mobile=username)
        else:
            user = User.objects.get(username=username)
    except User.DoesNotExist:
        return None
    else:
        return user


class UsernameMobileAuthBackend(ModelBackend):
    """自定义用户名或手机号认证"""
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = get_user_by_count(username)
        if user is  not None and user.check_password(password):
            return user
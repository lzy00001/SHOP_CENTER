from django.shortcuts import render

# Create your views here.
# url(r'^usernames/(?P<username>\w{5,20})/count/$', views.UsernameCountView.as_view()),
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User


# url(r'^users/$', views.UserView.as_view()),
from users.serializers import CreateUserSerializer


class UserView(CreateAPIView):
    """
    用户注册
    传入参数：
        username, password, password2, sms_code, mobile, allow
    """
    # 接受参数  校验参数   保存数据到数据库中   序列化器
    serializer_class = CreateUserSerializer
    # 返回响应


class UsernameCountView(APIView):
    """用户数量"""
    def get(self, request, username):
        count = User.objects.filter(username=username).count()

        data = {
            "username":username,
            "count":count,
        }
        return Response(data)


# url(r'^mobiles/(?P<mobile>1[3-9]\d{9})/count/$', views.MobileCountView.as_view()),
class MobileCountView(APIView):
    def get(self, request, mobile):
        count = User.objects.filter(mobile=mobile).count()

        data = {
            "mobile":mobile,
            "count":count,
        }
        return Response(data)

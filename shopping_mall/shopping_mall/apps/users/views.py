from django.shortcuts import render

# Create your views here.
# url(r'^usernames/(?P<username>\w{5,20})/count/$', views.UsernameCountView.as_view()),
from rest_framework import status
from rest_framework.generics import CreateAPIView, RetrieveAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User


# url(r'^users/$', views.UserView.as_view()),
from users.serializers import CreateUserSerializer, UserDetailSerializer, EmailSerializer


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


class UserDetailView(RetrieveAPIView):
    """用户详情页"""
    serializer_class = UserDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class EmailView(UpdateAPIView):
    """保存用户邮箱"""
    serializer_class = EmailSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class VerifyEmailView(APIView):
    """邮箱验证"""
    def get(self, request):
        """获取token"""
        token = request.query_params.get("token")
        if not token:
            return Response({"message":"缺少token"}, status=status.HTTP_400_BAD_REQUEST)

        # 校验token
        user = User.check_verify_email_token(token)
        if user is None:
            return Response({"messsage":"链接信息无效"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            user.email_active = True
            user.save()
            return Response({"message":"OK"})



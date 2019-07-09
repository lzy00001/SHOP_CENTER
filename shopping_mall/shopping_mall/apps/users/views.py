from django.shortcuts import render

# Create your views here.
# url(r'^usernames/(?P<username>\w{5,20})/count/$', views.UsernameCountView.as_view()),
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import CreateAPIView, RetrieveAPIView, UpdateAPIView
from rest_framework.mixins import CreateModelMixin, UpdateModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from goods.models import SKU
from users import constants
from users.models import User


# url(r'^users/$', views.UserView.as_view()),
from users.serializers import CreateUserSerializer, UserDetailSerializer, EmailSerializer, UserAddressSerializer, \
    AddressTitleSerializer, AddUserBrowsingHistorySerializer, SKUSerializer


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


class AddressViewSet(CreateModelMixin, UpdateModelMixin, GenericViewSet):
    """用户的新增、修改、删除、设置默认地址"""
    serializer_class = UserAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.request.user.addresses.filter(is_deleted=False)

    def list(self, request, *args, **kwargs):
        """用户地址列表更新"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        user = self.request.user
        return Response({
            "user_id":user.id,
            "default_addrss_id":user.default_address,   # 默认地址ID
            "limit":constants.USER_ADDRESS_COUNTS_LIMIT,
            "addresses":serializer.data,
        })

    def create(self, request, *args, **kwargs):
        """保存用户地址"""
        # 检查用户地址是否超过上限
        count = request.user.addresses.filter(is_delect=False).count()
        if count >= constants.USER_ADDRESS_COUNTS_LIMIT:
            return Response({"message":"保存地址数据已经达到上限"}, status=status.HTTP_400_BAD_REQUEST)
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """用户地址删除"""
        address = self.get_object()

        # 进行逻辑删除
        address.is_deleted = True
        address.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["put"], detail=True)
    def status(self, request, *args, **kwargs):
        address = self.get_object()
        request.user.default_address = address
        request.user.save()
        return Response({"message":"ok"}, status=status.HTTP_200_OK)

    @action(methods=["put"], detail=True)
    def title(self, request, *args, **kwargs):
        """修改标题"""
        address = self.get_object()
        serializer = AddressTitleSerializer(instance=address, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserBrowsingHistoryView(CreateAPIView):
    """
    用户浏览历史记录
    """
    serializer_class = AddUserBrowsingHistorySerializer
    permission_classes = [IsAuthenticated]


    def get(self, request):
        """获取浏览记录"""
        user_id = request.user.id

        # 查询redis  list
        redis_conn = get_redis_connection("history")
        sku_id_list = redis_conn.lrange("history_%s" % user_id, 0, constants.USER_BROWSE_HISTORY_MAX_LIMIT)

        # 遍历获取数据
        skus = []
        for sku_id in sku_id_list:
            sku = SKU.objects.get(id=sku_id)
            skus.append(sku)

        # 序列化返回
        serializer = SKUSerializer(skus, many=True)
        return Response(serializer.data)

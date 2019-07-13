from django.shortcuts import render

# Create your views here.
from rest_framework import status
from rest_framework.generics import GenericAPIView, CreateAPIView
from rest_framework.response import Response

from rest_framework.views import APIView
from rest_framework_jwt.settings import api_settings

from carts.utils import merge_cart_cookie_to_redis
from oauth.exceptions import OAuthQQAPIError
from oauth.models import OAuthQQUser
from oauth.serializers import OAuthQQUserSerializer

from oauth.utils import OAuthQQ


class QQAuthURLView(APIView):
    """获取QQ的url"""
    def get(self, request):
        next = request.query_params.get("next")
        oauth = OAuthQQ(state=next)
        login_url = oauth.get_qq_login_url()

        return Response({"login_url":login_url})


# class QQAuthUserView(GenericAPIView):
class QQAuthUserView(CreateAPIView):
    """QQ登录的用户"""
    serializer_class = OAuthQQUserSerializer
    def get(self, request):
        # 获取code
        code = request.query_params.get("code")
        if not code:
            return Response({"message":"缺少code"}, status=status.HTTP_400_BAD_REQUEST)

        oauth_qq = OAuthQQ()
        try:
            # 通过code获取access_token
            access_token = oauth_qq.get_access_token(code)

            # 通过access_token获取openid
            openid = oauth_qq.get_openid(access_token)
        except OAuthQQAPIError:
            return Response({"message":"访问QQ借口异常"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # 根据openid查询OAuthQQUser  是否有数据
        try:
            oauth_qq_use = OAuthQQUser.objects.get(openid=openid)
        except:
            # 如果数据不存在,处理openid并返回
            access_token = oauth_qq.generate_bind_user_access_token(openid)
            return Response({"access_token": access_token})
        else:
            # 数据存在,说明用户已经绑定身份,  签发JWT  token
            jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
            jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

            user = oauth_qq_use.user
            payload = jwt_payload_handler(user)
            token = jwt_encode_handler(payload)

            # return Response({
            #     'username': user.username,
            #     'user_id': user.id,
            #     'token': token
            # })
            response = Response({
                'username': user.username,
                'user_id': user.id,
                'token': token
            })

            # 添加合并购物车
            response = merge_cart_cookie_to_redis(request, user, response)
            return response

    # 数据不存在,创建用户,处理openid并返回
    # def post(self, request):
    #     serializer = self.get_serializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #     user = serializer.save()
    #
    #     response = Response({
    #         'token': user.token,
    #         'user_id': user.id,
    #         'username': user.username
    #     })
    #
    #     return response

    # 数据不存在,创建用户,处理openid并返回
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        # 合并购物车
        user = self.user
        response = merge_cart_cookie_to_redis(request, user, response)

        return response

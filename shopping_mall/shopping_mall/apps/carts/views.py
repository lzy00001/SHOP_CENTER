import base64
import pickle

from django.shortcuts import render

# Create your views here.
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from carts import constants
from carts.serializers import CartSerializer


class CartView(GenericAPIView):
    """购物车"""
    # 重写验证方法,不检查JWT_token
    def perform_authentication(self, request):
        pass

    serializer_class = CartSerializer

    def post(self, request):
        """添加商品到购物车内"""
        # 校验参数
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sku_id = serializer.validated_data['sku_id']
        count = serializer.validated_data['count']
        selected = serializer.validated_data['selected']

        # 判断用户是否登录
        try:
            user = request.user
        except Exception:
            user = None

        # 保存
        if user and user.is_authenticated:
            # 用户登录保存到redis中
            redis_conn = get_redis_connection("cart")
            pl = redis_conn.pipeline()

            # 保存添加到购物车的数量
            pl.hincrby("cart_%s" % user.id, sku_id, count)
            #　保存添加购物车的勾选项默认为勾选
            if selected:
                pl.sadd("cart_select_%s" % user.id, sku_id)
            pl.execute()

            # 返回相应
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            # 用户未登录保存到cookie中
            # 取出cookie中购物车数据
            cart = request.COOKIES.get("cart")
            if cart is not None:
                cart = pickle.loads(base64.b64decode(cart.encode()))
            else:
                cart = {}

            # 保存添加到购物车的数量
            sku = cart.get("count")
            if sku:
                count += int(sku.get("count"))

            # 　保存添加购物车的勾选项默认为勾选
            cart[sku_id] = {
                "count":count,
                "select":selected,
            }

            #对cart进行编码
            cookie_cart = base64.b64encode(pickle.dumps(cart)).decode()

            # 返回相应
            response = Response(serializer.data, status=status.HTTP_201_CREATED)

            # 设置购物车cookie
            response.set_cookie("cart", cookie_cart, max_age=constants.CART_COOKIE_EXPIRES)
            return response
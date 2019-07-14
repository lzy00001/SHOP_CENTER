import base64
import pickle

from django.shortcuts import render

# Create your views here.
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from carts import constants
from carts.serializers import CartSerializer, CartSKUSerializer,CartDeleteSerializer,CartSelectAllSerializer
from goods.models import SKU


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
                pl.sadd("cart_selected_%s" % user.id, sku_id)
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
                "selected":selected,
            }

            #对cart进行编码
            cookie_cart = base64.b64encode(pickle.dumps(cart)).decode()

            # 返回相应
            response = Response(serializer.data, status=status.HTTP_201_CREATED)

            # 设置购物车cookie
            response.set_cookie("cart", cookie_cart, max_age=constants.CART_COOKIE_EXPIRES)
            return response

    def get(self, request):
        """获取购物车商品信息"""
        # 判断用户是是否存在
        try:
            user = request.user
        except:
            user = None

        if user and user.is_authenticated:
            # 用户已登录,从redis中获取数据
            redis_conn = get_redis_connection("cart")
            redis_cart = redis_conn.hgetall("cart_%s" % user.id)
            redis_cart_selected = redis_conn.smembers("cart_selected_%s" % user.id)

            # 购物车内商品
            cart = {}
            for sku_id, count in redis_cart.items():
                cart[int(sku_id)] = {
                    "count":int(count),
                    "selected":sku_id in redis_cart_selected
                }
        else:
            # 用户未登录,从cookie中获取数据
            cart = request.COOKIES.get("cart")
            if cart is not None:
                cart = pickle.loads(base64.b64decode(cart.encode()))
            else:
                cart = {}

        # 遍历处理购物车数据
        skus = SKU.objects.filter(id__in=cart.keys())
        for sku in skus:
            sku.count = cart[sku.id]["count"]
            sku.selected = cart[sku.id]["selected"]

        # 序列化返回
        serializer = CartSKUSerializer(skus, many=True)
        return Response(serializer.data)

    def put(self, request):
        """修改购物车信息"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sku_id = serializer.validated_data.get('sku_id')
        count = serializer.validated_data.get('count')
        selected = serializer.validated_data.get('selected')

        # 尝试对请求的用户进行验证
        try:
            user = request.user
        except Exception:
            # 验证失败，用户未登录
            user = None

        if user and user.is_authenticated:
            # 用户已经登录,在redis中保存
            redis_conn = get_redis_connection("cart")
            pl = redis_conn.pipeline()
            pl.hset("cart_%s" % user.id, sku_id, count)
            if selected:
                pl.sadd("cart_selected_%s" % user.id, sku_id)
            else:
                pl.srem('cart_selected_%s' % user.id, sku_id)
            pl.execute()

            return Response(serializer.data)
        else:
            # 用户未登录,保存在cookie中
            cart = request.COOKIES.get("cart")
            if cart:
                cart = pickle.loads(base64.b64decode(cart.encode()))
            else:
                cart = {}
            cart[sku_id] = {
                "count":count,
                "selected":selected,
            }
            cookie_cart = base64.b64encode(pickle.dumps(cart)).decode()
            response = Response(serializer.data)

            # 设置购物车cookie
            response.set_cookie("cart", cookie_cart, max_age=constants.CART_COOKIE_EXPIRES)
            return response

    def delete(self, request):
        """删除购物车商品"""
        serializer = CartDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sku_id = serializer.validated_data["sku_id"]

        try:
            user = request.user
        except:
            user = None

        if user and user.is_authenticated:
            # 用户已经登录,在redis中删除
            redis_conn = get_redis_connection("cart")
            pl = redis_conn.pipeline()
            pl.hdel("cart_%s" % user.id, sku_id)
            pl.srem("car_selected_%s" % user.id, sku_id)
            pl.execute()

            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            # 用户未登录,在cookie中删除
            cart = request.COOKIES.get("cart")
            response = Response(status=status.HTTP_204_NO_CONTENT)
            if cart:
                cart = pickle.loads(base64.b64decode(cart.encode()))
                if sku_id in cart:
                    del cart[sku_id]
                    cookie_cart = base64.b64encode(pickle.dumps(cart)).decode()
                    # 保存cookie
                    response.set_cookie("cart", cookie_cart, max_age=constants.CART_COOKIE_EXPIRES)

            return response


class CartSelectAllView(GenericAPIView):
    """购物车全选"""

    def perform_authentication(self, request):
        pass

    serializer_class = CartSelectAllSerializer

    def put(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        selected = serializer.validated_data["selected"]

        try:
            user = request.user
        except Exception:
            user = None

        if user and user.is_authenticated:
            redis_conn = get_redis_connection("cart")
            cart = redis_conn.hgetall("cart_%s" % user.id)
            sku_id_list = cart.keys()

            if selected:
                redis_conn.sadd("cart_selected_%s" % user.id, *sku_id_list)
            else:
                redis_conn.srem("cart_selected_%s" % user.id, *sku_id_list)

            return Response({"message":"ok"})
        else:
            cart = request.COOKIES.get("cart")
            response = Response({"message":"ok"})
            if cart:
                cart = pickle.loads(base64.b64decode(cart.encode()))
                for sku_id in cart:
                    cart[sku_id]["selected"] = selected
                cookie_cart = base64.b64encode(pickle.dumps(cart)).decode()

                # 保存cookies
                response.set_cookie("cart", cookie_cart, max_age=constants.CART_COOKIE_EXPIRES)

            return response
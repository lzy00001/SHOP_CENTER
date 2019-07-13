import pickle
import base64

from django_redis import get_redis_connection


def merge_cart_cookie_to_redis(request, user, response):
    """
    合并请求用户的购物车,将未登录保存在cookie里的保存在redis中
    :param request: 用户的请求对象
    :param user: 当前登录的用户
    :param response: 响应对象,用于清除购物车的cookie
    :return:
    """
    # 获取cookie中购物车的信息
    cookie_str = request.COOKIES.get("cart")
    if not cookie_str:
        return response
    cookie_dict = pickle.loads(base64.b64decode(cookie_str.encode()))

    # 取出存在redis中信息
    redis_conn = get_redis_connection("cart")
    redis_cart = redis_conn.hgetall("cart_%s" % user.id)
    redis_cart_selected = redis_conn.smembers("cart_selected_%s" % user.id)

    # 设置一个空字典用与保存最新redis信息
    cart = {}
    for sku_id, count in redis_cart.items():
        cart[int(sku_id)] = int(count)

    for sku_id, count_selecte_dict in cookie_dict.items():
        cart[sku_id] = count_selecte_dict["count"]
        if count_selecte_dict["selected"]:
            redis_cart_selected.add(sku_id)

    # 保存最新的购物车信息到redis中
    if cart:
        pl = redis_conn.pipeline()
        pl.hmset("cart_%s" % user.id, cart)
        pl.sadd("cart_selected_%s" % user.id, *redis_cart_selected)
        pl.execute()

    response.delete_cookie("cart")

    return response




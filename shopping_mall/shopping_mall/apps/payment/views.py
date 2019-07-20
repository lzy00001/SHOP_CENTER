import os
from alipay import AliPay
from django.conf import settings
from django.shortcuts import render
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

# Create your views here.
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import OrderInfo
from payment.models import Payment


class Paymentview(APIView):
    """支付"""
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=request.user,
                                          pay_method=OrderInfo.PAY_METHODS_ENUM["ALIPAY"],
                                          status=OrderInfo.ORDER_STATUS_ENUM["UNPAID"])
        except OrderInfo.DoesNotExist:
            return Response({"message":"订单信息有误"}, status = status.HTTP_400_BAD_REQUEST)

        # 构造支付宝的链接地址
        alipy = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys/app_private_key.pem"),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys/alipay_public_key.pem"),  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False
        )

        # 电脑网站支付，需要跳转到https://openapi.alipay.com/gateway.do? + order_string
        order_string = alipy.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(order.total_amount),
            subject="美多商城%s" % order_id,
            return_url="http://www.meiduo.site:8080/pay_success.html",
        )

        # 拼接支付链接网址
        alipay_url =settings.ALIPAY_URL + "?" + order_string
        return Response({"alipay_url":alipay_url})


# PUT /payment/status/?支付宝参数
# charset=utf-8
# &out_trade_no=20180704082900000000001
# &method=alipay.trade.page.pay.return
# &total_amount=3788.00
# &trade_no=2018070421001004630200569950
# &auth_app_id=2016081600258081
# &version=1.0&app_id=2016081600258081&sign_type=RSA2&seller_id=2088102171419163&timestamp=2018-07-04+16%3A31%3A49

# &sign=UNn3nCckqp4E3MJAonwiywZBtP5Wiia6eJVUta0iimZeLdUuMhH%2FdyRmPGgaQ6xHn0u5KCQbeof4dsXyh%2FdG42cLho9LYCcRqwa6qv3BbEx1J3Y9Qxp6ye%2BTmQq9UbW3%2FoXdAjVJ0gChPQNjm%2BCMI0XbLPT9ARyclb3oKMHrNB7kixMma8OIQbztylSbIwnQilQlxhIWzDqhxCXRgAXjRir7748YpkzW%2FlpkTyuxU1mKI4VwvxV8Of4PQqZcLU%2BbXo2SI%2Bm0Vy%2FgMae4hZIRf%2BbTI1C8lw203HpOMDDeZiUea3GpF9WzuZkTPc4Ryv%2F8K3F6e2IvInpeQt48nqNC%2BQ%3D%3D


class PaymentStatusView(APIView):
    """支付结果"""
    def put(self, request):
        data = request.query_params.dict()
        signature = data.pop("sign")

        alipay =  AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调函数
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys/app_private_key.pem"),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "keys/alipay_public_key.pem"),  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False
        )

        # signature和data比较
        success = alipay.verify(data, signature)

        if success:
            # 订单编号
            order_id = data.get("out_trade_no")
            # 支付宝支付流水号
            trade_id = data.get("trade_no")

            # 保存支付结果数据
            Payment.objects.create(
                order_id=order_id,
                trade_id=trade_id,
            )

            # 修改订单状态
            OrderInfo.objects.filter(order_id=order_id, status=OrderInfo.ORDER_STATUS_ENUM["UNPAID"]).update(status=OrderInfo.ORDER_STATUS_ENUM["UNCOMMENT"])
            return Response({"trade_id":trade_id})
        else:
            return Response({"message":"参数有误"}, status=status.HTTP_400_BAD_REQUEST)


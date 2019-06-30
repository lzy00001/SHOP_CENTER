import random

from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from rest_framework.views import APIView
import logging
from celery_tasks.sms.tasks import send_sms_code

from shopping_mall.libs.captcha.captcha import captcha
from shopping_mall.utils.yuntongxun.sms import CCP
from verifications import constants
from verifications.serializers import ImageCodeCheckSerializer


logger = logging.getLogger('django')


class ImageCodeView(APIView):
    """图片验证码"""
    def get(self, request, image_code_id):
        # 接受参数       （获取图片验证码）
        # 校验参数       （校验图片验证码）
        # 由于参数image_code_id在url路由中正则可以校验,所以不用考虑接受参数和校验参数

        # 生成图片验证码
        text, image = captcha.generate_captcha()

        # 保存图片验证码到redis中～文本格式
        # 1.连接redis
        redis_conn = get_redis_connection('verify_codes')
        # 2.保存图片验证码到redis中
        redis_conn.setex("img_%s" % image_code_id, constants.IMAGE_CODE_REDIS_EXPIRES, text)

        # 返回图片验证码     （返回图片验证码获取成功响应）
        return HttpResponse(image, content_type="images/jpg")


class SMSCodeView(GenericAPIView):
    """
    短信验证码
    传入参数：
        mobile,     image_code_id, text
    """
    serializer_class = ImageCodeCheckSerializer

    def get(self, request, mobile):
        # 校验参数  由序列化器完成
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        # 生成短信验证码
        sms_code = '%06d' % random.randint(0, 999999)

        # 保存短信验证码  保存发送记录
        redis_conn = get_redis_connection('verify_codes')
        # redis_conn.setex("sms_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        # redis_conn.setex("send_flag_%s" % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)

        # redis管道
        pl = redis_conn.pipeline()
        pl.setex("sms_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        pl.setex("send_flag_%s" % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)

        # 让管道通知redis执行命令
        pl.execute()

        # # 发送短信
        # try:
        #     ccp = CCP()
        #     expires = constants.SMS_CODE_REDIS_EXPIRES // 60
        #     result = ccp.send_template_sms(mobile, [sms_code, expires], constants.SMS_CODE_TEMP_ID)
        # except Exception as e:
        #     logger.error("发送验证码短信[异常][ mobile: %s, message: %s ]" % (mobile, e))
        #     return Response({'message': 'failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # else:
        #     if result == 0:
        #         logger.info("发送验证码短信[正常][ mobile: %s ]" % mobile)
        #         return Response({'message': 'OK'})
        #     else:
        #         logger.warning("发送验证码短信[失败][ mobile: %s ]" % mobile)
        #         return Response({'message': 'failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 使用celery发送短信验证码
        expires = constants.SMS_CODE_REDIS_EXPIRES // 60
        send_sms_code.delay(mobile, sms_code, expires, constants.SMS_CODE_TEMP_ID)

        return Response({'message': 'OK'})
from django_redis import get_redis_connection
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings

from .models import OAuthQQUser
from oauth.utils import OAuthQQ
from users.models import User


class OAuthQQUserSerializer(serializers.ModelSerializer):
    mobile = serializers.RegexField(label="手机号", regex=r'^1[3-9]\d{9}$')
    sms_code = serializers.CharField(label="短信验证码", write_only=True)
    access_token = serializers.CharField(label="操作凭证", write_only=True)
    token = serializers.CharField(label="JWTtoken", read_only=True)

    class Meta:
        model = User
        fields = ("mobile", "password", "sms_code", "access_token", "token", "id", "username")
        extra_kwargs = {
            "username":{
                "read_only":True
            },
            'password': {
                'write_only': True,
                'min_length': 8,
                'max_length': 20,
                'error_messages': {
                    'min_length': '仅允许8-20个字符的密码',
                    'max_length': '仅允许8-20个字符的密码',
                }
            }
        }

    # 校验参数
    def validate(self, attrs):
        # 校验access_token
        access_token = attrs["access_token"]
        openid = OAuthQQ.check_bind_user_access_token(access_token)
        if not openid:
            return serializers.ValidationError("无效的")

        # 将openid保存到atters中
        attrs["openid"] = openid

        #　校验短信验证码
        mobile = attrs["mobile"]
        sms_code = attrs["sms_code"]
        redis_conn = get_redis_connection("verify_codes")
        real_sms_code = redis_conn.get("sms_%s" % mobile)
        if sms_code != real_sms_code.decode():
            raise serializers.ValidationError("短信验证码错误")

        # 判断用户是否存在,若存在校验密码
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            pass
        else:
            password = attrs["password"]
            if not user.check_password(password):
                raise serializers.ValidationError("密码错误")

            attrs["user"] = user
        return attrs

    def create(self, validated_data):
        openid = validated_data['openid']
        mobile = validated_data["mobile"]
        user = validated_data["user"]
        password = validated_data["password"]

        # 判断用户是否存在
        if not user:
            # 如果不存在,先创建user, 再创建OAuthQQUser
            user = User.objects.create_user(username=mobile, mobile=mobile,password=password)

        # 如果存在,绑定,创建OAuthQQUser
        OAuthQQUser.objects.create(user=user, openid=openid)

        # 签发JWT token
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

        payload = jwt_payload_handler(user)
        token = jwt_encode_handler(payload)

        user.token = token

        return user




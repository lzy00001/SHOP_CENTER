import re

from django_redis import get_redis_connection
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings

from celery_tasks.email.tasks import send_verify_email
from goods.models import SKU
from users import constants
from users.models import User, Address


class CreateUserSerializer(serializers.ModelSerializer):
    """注册序列化器"""
    password2 = serializers.CharField(label="确认密码", write_only=True)
    sms_code = serializers.CharField(label="短信验证码", write_only=True)
    allow = serializers.CharField(label="同意协议", write_only=True)
    token = serializers.CharField(label="登录状态token", read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'password2', 'sms_code', 'mobile', 'allow', "token")
        extra_kwargs = {
            "username":{
                "min_length":5,
                "max_length":20,
                "error_messages":{
                    "min_length":"仅允许5-20个字符的用户",
                    "max_length":"仅允许5-20个字符的用户",
                }

            },
            "password":{
                "write_only":True,
                "min_length":6,
                "max_length":20,
                "error_messages":{
                    "min_length": "密码必须为6-20位",
                    "max_length": "密码必须为6-20位",
                }
            }

        }

    # 验证手机号  （为了避免用户接受手机验证码后更改手机号，增加手机号验证）
    def validate_mobile(self, value):
        if not re.match(r'^1[3-9]\d{9}$', value):
            return serializers.ValidationError("手机号格式错误")
        return value

    def validate(self, data):
        # 判断两次密码是否相等
        if data["password"] != data["password2"]:
            return serializers.ValidationError("两次输入密码不一致")

        # 判断短信验证码是否和数据库中一样
        redis_conn = get_redis_connection("verify_codes")
        real_sms_code = redis_conn.get("sms_%s" % data["mobile"])
        if not real_sms_code:
            return serializers.ValidationError("无效的验证码")

        if real_sms_code.decode() != data["sms_code"]:
            raise serializers.ValidationError("短信验证码错误")

        return data

    # 判断是同意使用协议
    def validate_allow(self, value):
        if value != "true":
            return serializers.ValidationError("请同意用户协议")
        return value

    # 创建用户    （保存到数据库中）
    def create(self, validate_data):
        del validate_data["password2"]
        del validate_data["sms_code"]
        del validate_data["allow"]
        user = super().create(validate_data)

        # 调用django的认证系统对密码加密
        user.set_password(validate_data["password"])
        user.save()

        # 补充生成记录状态token
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

        payload = jwt_payload_handler(user)
        token = jwt_encode_handler(payload)

        user.token = token

        return user


class UserDetailSerializer(serializers.ModelSerializer):
    """用户详情信息序列化器"""
    class Meta:
        model = User
        fields = ("id", "username", "mobile", "email", "email_active")


class EmailSerializer(serializers.ModelSerializer):
    """邮箱序列化"""
    class Meta:
        model = User
        fields = ("id", "email")
        extra_kwargs = {
            "email":{
            "required": True
            }
        }

    def update(self, instance, validated_data):
        """

        :param instance: 视图传过来的对象
        :param validated_data:
        :return:
        """
        email = validated_data["email"]
        # 保存
        instance.email = email
        instance.save()

        verify_url = instance.generate_verify_email_url()

        send_verify_email.delay(email, verify_url)
        return instance


class UserAddressSerializer(serializers.ModelSerializer):
    """用户地址的序列化器"""
    province = serializers.StringRelatedField(read_only=True)
    city = serializers.StringRelatedField(read_only=True)
    district = serializers.StringRelatedField(read_only=True)
    province_id = serializers.IntegerField(label='省ID', required=True)
    city_id = serializers.IntegerField(label='市ID', required=True)
    district_id = serializers.IntegerField(label='区ID', required=True)

    class Meta:
        model = Address
        exclude = ("user", "is_deleted", "create_time", "update_time")

    def validate_mobile(self, value):
        """验证手机号"""
        if not re.match(r"^1[3-9]\d{9}$", value):
            raise serializers.ValidationError("手机号格式错误")
        return value

    def create(self, validated_data):
        """保存信息"""
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class AddressTitleSerializer(serializers.ModelSerializer):
    """地址标题"""
    class Meta:
        model = Address
        fields = ("title",)


class AddUserBrowsingHistorySerializer(serializers.Serializer):
    """添加用户浏览历史序列器化"""
    sku_id = serializers.IntegerField(label="商品sku编号", min_value=1)

    def validate_sku_id(self, value):
        try:
            SKU.objects.get(id=value)
        except SKU.DoesNotExist:
            raise serializers.ValidationError("该商品不存在")
        return value

    def create(self, validated_data):
        sku_id = validated_data["sku_id"]
        user = self.context["request"].user

        redis_conn = get_redis_connection("history")
        pl = redis_conn.pipeline()
        redis_key = "history_%s" % user.id

        # 去重
        pl.lrem(redis_key, 0, sku_id)

        # 保存
        pl.lpush(redis_key, sku_id)

        # 截断
        pl.ltrim(redis_key, 0, constants.USER_BROWSE_HISTORY_MAX_LIMIT-1)

        # redis管道处理任务
        pl.execute()

        return validated_data


class SKUSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKU
        fields = ('id', 'name', 'price', 'default_image_url', 'comments')
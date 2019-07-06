from rest_framework import serializers

from areas.models import Area


class AreaSerializer(serializers.ModelSerializer):
    """省级序列化器"""
    class Meta:
        model = Area
        fields = ("id", "name")


class SubAreaSerializer(serializers.ModelSerializer):
    """"地区序列化器"""
    subs = AreaSerializer(many=True, read_only=True)
    class Meta:
        model = Area
        fields = ("id", "name", "subs")
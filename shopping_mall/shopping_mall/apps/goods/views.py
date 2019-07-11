from django.db.models import Q
from django.shortcuts import render

# Create your views here.
from rest_framework.filters import OrderingFilter
from rest_framework.generics import ListAPIView

from goods.models import SKU
from goods.serializers import SKUSerializer


# /categories/(?P<category_id>\d+)/skus?page=xxx&page_size=xxx&
class SKUListView(ListAPIView):
    serializer_class = SKUSerializer
    # 分页操作  直接在配置文件中设置

    # 排序
    filter_backends = (OrderingFilter,)
    ordering_fields = ("create_time", "price", "sales")

    def get_queryset(self):
        category_id = self.kwargs["category_id"]
        # a = SKU.objects.filter(is_launched=True)[0]
        # b = a.category_id
        # b = type(b)
        # c = a.category
        return SKU.objects.filter(category_id=category_id, is_launched=True)


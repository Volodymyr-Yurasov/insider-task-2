from rest_framework import serializers


class RoundedFloatField(serializers.FloatField):
    def __init__(self, *, decimals: int = 2, **kwargs):
        self.decimals = decimals
        super().__init__(**kwargs)

    def to_representation(self, value):
        return round(float(value), self.decimals)

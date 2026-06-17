from rest_framework import serializers
from .models import FeeCategory, FeeStructure, StudentFee, Payment

class FeeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeCategory
        fields = ['id', 'name', 'description']

class FeeStructureSerializer(serializers.ModelSerializer):
    fee_category = serializers.CharField(source='fee_category.name')
    class Meta:
        model = FeeStructure
        fields = ['id', 'fee_category', 'amount', 'academic_year', 'grade_level']

class StudentFeeSerializer(serializers.ModelSerializer):
    fee_structure = FeeStructureSerializer()
    student = serializers.CharField(source='student.username')
    class Meta:
        model = StudentFee
        fields = ['id', 'student', 'fee_structure', 'due_date', 'is_paid']

class PaymentSerializer(serializers.ModelSerializer):
    student_fee = serializers.IntegerField(source='student_fee.id')
    class Meta:
        model = Payment
        fields = ['id', 'student_fee', 'amount_paid', 'payment_date', 'transaction_id', 'payment_method']

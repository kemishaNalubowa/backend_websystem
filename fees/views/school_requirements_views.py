from django.shortcuts import render, redirect
from django.urls import reverse
from fees.models import ScholasticRequirementClass,SchoolScholasticRequirements,StudentScholasticRequirementStatus
from academics.utils.subject_utils import get_sch_supported_classes



def add_scholasticc_requirements(request):
    if  request.methos == 'POST':

        submitted_data = {}

        submitted_data['classes_chosen'] =[]

        for cls in get_sch_supported_classes():
            class_ = (request.POST.get(f"class_{cls.supported_class.key.lower()}") or '').strip()
            if class_:
                submitted_data['classes_chosen'].append(cls.pk)
        
        


            



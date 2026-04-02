from django.shortcuts import render, redirect
from django.urls import reverse
from academics.models import SchoolSupportedClasses, SchoolClass
from django.contrib import messages



def school_supported_classes_form(request):
    classes = SchoolClass.objects.all()

    if request.method == 'POST':
        submitted_data = []
        total_classes_supported =0
        
        for c in classes:
            class_ = request.POST.get(f"class_{c.key}")

            if class_ == c.key:
                submitted_data.append(c)

        for s in submitted_data:
            if not SchoolSupportedClasses.objects.filter(supported_class=s).first():
                SchoolSupportedClasses.objects.create(
                    supported_class = s
                )
                total_classes_supported +=1

        messages.success(request, f"{total_classes_supported} Classes are now supported by your School")
        return redirect(reverse("dashboard"))
    return render(request, "academics/class/school_supported_classes_form.html", {
        "classes":classes
    })


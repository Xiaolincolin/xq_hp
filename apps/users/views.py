import csv
import math
from itertools import combinations

import random
import string

from collections import OrderedDict, defaultdict
from django.contrib.auth.handlers.modwsgi import check_password
from django.contrib.auth.hashers import make_password
from django.shortcuts import render
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q, Sum, F, Count
from django.views.generic import View

from madmin.models import Assist, AssistTeacher, AssociateCourseGrade, AssociateCourse, AssociateGender, Associateaward, \
    Associate_native_place, AssociateGrade, AssociateBook
from reposityory.models import HotJob, Artcle, HotProject
from .forms import LoginForm
from .models import MyMessage, AssitStudy
from courese.models import MajorSystem,StGgrade,LearnWarning
from xq_type.models import personal_type, Types, Technologys
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from courese.models import WarnRule
from users.models import UserProfile
import json
from django.views.decorators.csrf import csrf_exempt
# Create your views here.
#配置登录名可以是邮箱
class CustomBackend(ModelBackend):
    def authenticate(self, username=None, password=None, **kwargs):
        try:
            user = UserProfile.objects.get(Q(username=username) | Q(email=username))
            if user.check_password(password):
                return user
        except Exception as e:
            return None


#退出登录
class LogoutView(View):
    """
    用户退出
    """
    def get(self, request):
        logout(request)
        from django.urls import reverse
        return HttpResponseRedirect(reverse("login"))


#登录逻辑
class LoginView(View):
    def get(self,request):
        return render(request, "others/login.html", {})

    def post(self,request):
        login_form = LoginForm(request.POST)
        if login_form.is_valid():
            user_name = request.POST.get("username", "")
            pass_word = request.POST.get("password", "")
            get_admin = request.POST.get("is_admin", "")

            user = authenticate(username=user_name, password=pass_word)
            if user is not None:
                dbadmin = UserProfile.objects.get(username=user_name)
                if get_admin == dbadmin.is_admin and get_admin == "stu":
                    login(request, user)
                    return HttpResponseRedirect('/main/')
                elif get_admin == dbadmin.is_admin and get_admin == "admin":
                    login(request,user)
                    return HttpResponseRedirect('/admindex/')
                else:
                    return render(request, 'others/login.html', {"msg": "用户名或密码错误！"})
            else:
                return render(request, "others/login.html", {"msg": "用户名或密码错误！"})

        else:
            return render(request, "others/login.html", {"login_form": "用户名或密码错误！"})


class MyMessageView(View):
    def get(self,request):
        if request.user.is_authenticated:
            student_number = request.user
            info = MyMessage.objects.get(st_id=request.user)
            #预警等级
            student_warm_leves = LearnWarning.objects.filter(st_id=info.id).order_by('add_time').values('level')
            if(len(student_warm_leves)>0):
                student_warm_leve = str((student_warm_leves[0])['level'])
            else:
                student_warm_leve = ''
            #总学分
            sum =MajorSystem.objects.filter(major=info.major).aggregate(sums=Sum('sum_credit'))
            sum_credit = sum['sums']
            #已修学分
            finished = StGgrade.objects.filter(st_id=info,grade__gte=60).aggregate(finished_credit_sum=Sum('credit'))
            finished_credit = finished['finished_credit_sum']
            if(finished_credit == None):
                finished_credit = 0
            #未修学分
            try:
                not_credit = sum_credit-finished_credit
            except:
                not_credit=0
            #挂科学分id __gt
            fail_exam = StGgrade.objects.filter(st_id=info,grade__lt=60).aggregate(grade_sum=Sum('credit'))
            fail_exam_sum = fail_exam['grade_sum']
            if fail_exam_sum == None:
                fail_exam_sum=0

            #查询的是所有成绩的学期和学分，加annotate以到达分组的目的，不然会有重复的学年出现
            once_year = StGgrade.objects.filter(st_id=info).values('year').annotate(year_Sum=Sum('credit'))
            once_semester = StGgrade.objects.filter(st_id=info).values_list('year','semester').annotate(year_Sum=Sum('credit'))
            # 反向查询，外键不能直接查询，获取个人信息表中学号的id
            #对应的学号
            st_id_info = info.id

            #获取制定的预警消息，并将每一学期，在校期间挂科学分加入列表，之后加入学生挂科的学分排序，获取前一个学分，再对应预警等级
            creadit_rule = WarnRule.objects.values_list('sum_credit','all_credit')
            once_semester_list = []
            all_year = []
            for index in creadit_rule:
                once_semester_list.append(index[0])
                all_year.append(index[1])


            #声明
            save_warm = LearnWarning()


            #(每一学期)首先统计每学期挂科的学分给出预警消息，分别查看每一学年的预警是否存在
            if(len(once_semester)>0):
                for semesters in once_semester:
                    #查看预警消息是否存在
                    has = LearnWarning.objects.filter(st_id_id=st_id_info, year=semesters[0],semester=semesters[1])

                    #查询这一学年是否有挂科
                    creadit_list = StGgrade.objects.filter(st_id=info,year=semesters[0], semester=semesters[1],grade__lt=60).values('year').annotate(sem_Sum=Sum('credit'))

                    #如果有挂科
                    if (len(creadit_list)>0):
                        # 如果不存在则添加一条预警消息
                        if (len(has) == 0):
                            sem_sum_creadit = (creadit_list[0])['sem_Sum']
                            sem_sum = (creadit_list[0])['sem_Sum']+0.0005  #加小数是为了防止数据的临界值
                            once_semester_list.append(sem_sum)
                            once_semester_list.sort()
                            sem_index = once_semester_list.index(sem_sum)
                            #获取到对应预警学分
                            if sem_index != 0:
                                warm_level_creadit = once_semester_list[sem_index-1]
                                #对应的预警等级
                                get_warm_level = WarnRule.objects.get(sum_credit=warm_level_creadit)
                                #将预警消息保存到数据库
                                save_warm.st_id_id=st_id_info
                                save_warm.name = info.name
                                save_warm.level =str(get_warm_level)
                                save_warm.warm_creadit = sem_sum_creadit
                                save_warm.college = info.college
                                save_warm.major = info.major
                                save_warm.myclass = info.myclass
                                save_warm.year = semesters[0]
                                save_warm.semester = semesters[1]
                                save_warm.message = str(semesters[0])+str(semesters[1])+"挂科学分为"+str(sem_sum_creadit)+"达到"+str(get_warm_level)
                                save_warm.save()

                    elif len(creadit_list)==0 and len(has) > 0:
                        #预警消息存在，又没有挂科，说明补考过了，删除预警等级
                        LearnWarning.objects.filter(st_id_id=st_id_info,year=semesters[0],semester=semesters[1]).delete()

            #在校期间是预警消息是否存在
            has_exist = LearnWarning.objects.filter(st_id_id=st_id_info,year='在校期间',warm_creadit = fail_exam_sum).all()

            #(在校期间)挂科总学分
            if(len(fail_exam)>0):
                if len(has_exist)==0:
                    fail_creadit = fail_exam_sum+0.005
                    all_year.append(fail_creadit)
                    all_year.sort()
                    creadit_index = all_year.index(fail_creadit)
                    # 获取到对应预警学分
                    if creadit_index != 0:
                        warm_level_creadit = all_year[creadit_index-1]
                        # 对应的预警等级
                        get_warm_level = WarnRule.objects.filter(all_credit=warm_level_creadit).values('level')
                        get_warm_level_name = (get_warm_level[0])['level']

                        #将数据保存入数据库
                        save_warm.st_id_id = st_id_info
                        save_warm.name = info.name
                        save_warm.level = get_warm_level_name
                        save_warm.warm_creadit = fail_exam_sum
                        save_warm.college = info.college
                        save_warm.major = info.major
                        save_warm.myclass = info.myclass
                        save_warm.year = '在校期间'
                        save_warm.semester = '在校期间'
                        save_warm.message = '在校期间' + "挂科学分为" + str(fail_exam_sum) + "达到" + str(get_warm_level_name)
                        save_warm.save()
            elif len(fail_exam) ==0 and len(has_exist)>0:
                LearnWarning.objects.filter(st_id_id=st_id_info,year='在校期间',warm_creadit = fail_exam_sum ).delete()

            #将预警消息推送到前端页面
            all_warn = LearnWarning.objects.all()

            #学情分析结果
            sum_result = personal_type.objects.filter(st_id=request.user).values('click_times').aggregate(sum=Sum('click_times'))
            max_f = personal_type.objects.all().filter(st_id=request.user)
            try:
                max_list = max_f.order_by('-click_times')[:4].values('click_times')
                max_names = max_f.order_by('-click_times')[:4].values('type_name')
                max_name = []
                for name in max_names:
                    tp_name = Types.objects.filter(id=name['type_name']).values('type_name')
                    max_name.append(tp_name[0])

                list_value = [1,1,1,1]
                list_key = ['暂无','暂无','暂无','暂无']
                if(len(max_list) and len(sum_result) != 0):
                    for r_item in range(4):
                        list_key[r_item] = max_name[r_item]['type_name']
                        list_value[r_item] = (float(max_list[r_item]['click_times'])/float(sum_result['sum']))
                else:
                    list_result=[1,1,1,1]
                for p in range(4):
                    list_value[p] = round(list_value[p] * 100, 2)
            except:
                list_value = [1, 1, 1, 1]
                list_key = ['暂无', '暂无', '暂无', '暂无']

            #所有挂科科目详情
            all_faile_courese = []
            fail_courese = StGgrade.objects.filter(st_id=request.user,grade__lt=60).values_list('year','semester','title','credit','grade')
            for cor in fail_courese:
                all_faile_courese.append(list(cor))

            #帮扶计划
            assist = Assist.objects.filter(st_id=request.user).values('job_number_id')
            #帮扶老师信息
            assist_teacher_info=[]
            if(len(assist)>0):
                assist_teacher = AssistTeacher.objects.filter(id=(assist[0])['job_number_id']).values_list('name','phone','major','assist_address')
                if(len(assist_teacher)>0):
                    assist_teacher_info = list(assist_teacher[0])

            s = string.ascii_letters
            code = random.choice(s)
            AssitStudy.objects.filter(number=request.user).update(rangeCode=code)

            #资讯，招聘推荐
            all_job=[]
            all_artcle=[]
            all_types = []
            # 如果已经确定方向，根据选择的类随机推荐
            sure_interest = MyMessage.objects.filter(st_id=request.user).values('favor')
            #没确定方向
            try:
                if (sure_interest[0])['favor']=='':
                    sure_interest = personal_type.objects.filter(st_id=request.user).values('type_name')
                    #如果没确定方向，也没点击过任何文章
                    if (sure_interest[0])['type_name']=='':
                        all_job = HotJob.objects.all().order_by('click_times')[0:15]
                        all_artcle = Artcle.objects.all().order_by('click_times')[0:15]
                        all_types = Types.objects.all().order_by('click_times')[0:15]
                    #如果点击过，根据点击过得类随机推荐
                    else:

                        type_id = []
                        for i in sure_interest:
                            type_id.append(i['type_name'])
                        range_id = random.choice(type_id)
                        all_job = HotJob.objects.filter(type_name_id=range_id).all().order_by('click_times')[0:15]
                        all_artcle = Artcle.objects.filter(type_name_id=range_id).all().order_by('click_times')[0:15]
                        all_types = Types.objects.all().order_by('click_times')[0:15]

                else:
                    tp_name = Types.objects.filter(type_name=(sure_interest[0])['favor']).values('id')
                    range_id = (tp_name[0])['id']
                    all_job = HotJob.objects.filter(type_name_id=range_id).all().order_by('click_times')[0:15]
                    all_artcle = Artcle.objects.filter(type_name_id=range_id).all().order_by('click_times')[0:15]
                    all_types = Types.objects.all().order_by('click_times')[0:15]
            except:
                all_job = HotJob.objects.all().order_by('click_times')[0:15]
                all_artcle = Artcle.objects.all().order_by('click_times')[0:15]
                all_types = Types.objects.all().order_by('click_times')[0:15]
            key1 = list_key[0]
            key2 = list_key[1]
            key3 = list_key[2]
            key4 = list_key[3]
            #生成随机码
            range_code = random.randint(10000, 99999)
            AssitStudy.objects.filter(number=request.user).update(rangeCode=range_code)

            #涉及技能
            tc_List = ''
            type_id = Types.objects.filter(type_name=info.favor).values('id')
            try:
                tc = Technologys.objects.filter(type_name_id=(type_id[0])['id']).values('name')
                for i in tc:
                    tc_List += i['name'] + '\t'
            except:
                tc_List=''
            #涉及招聘
            try:
                tc = HotJob.objects.filter(type_name_id=(type_id[0])['id'])[0]
                job_List = tc
            except:
                job_List=''

            login_user = request.user
            if str(login_user)=="20162056":
                login_user=1
                print(login_user)


            return render(request, 'stu/main.html',{
                'info':info,
                'sum_credit':json.dumps(sum_credit),
                'finished_credit':json.dumps(finished_credit),
                'not_credit':json.dumps(not_credit),
                'fail_exam_sum':json.dumps(fail_exam_sum),
                'all_warn':all_warn,
                'key1':key1 ,
                'value1':list_value[0],
                'key2': key2,
                'value2': list_value[1],
                'key3': key3,
                'value3': list_value[2],
                'key4': key4,
                'value4': list_value[3],
                'student_number':json.dumps(str(student_number),ensure_ascii=False),
                'student_warm_leve':json.dumps(str(student_warm_leve),ensure_ascii=False),
                'all_faile_courese': json.dumps(all_faile_courese),
                'assist_teacher_info':json.dumps(assist_teacher_info),
                'code':code,
                "all_job": all_job,
                "all_artcle": all_artcle,
                'all_types': all_types,
                'range_code':range_code,
                'tc_List':tc_List,
                'job_List':job_List,
                'login_user':login_user,
                })
        else:
            return HttpResponseRedirect('/')

#确定方向
class ConfirmInterestView(View):

    def post(self,request):
        if request.user.is_authenticated:
            mychoice = request.POST.get('choice','')
            student_number = request.POST.get('student_number','')
            MyMessage.objects.filter(st_id=student_number).update(favor=mychoice)
            json_data = {'message':'成功'}

            return JsonResponse(json_data)
        else:
            return HttpResponseRedirect('/')


#助学到学情自动登录实现
class AutoLogin(View):

    def get(self,request,id,username,code):
        if code!=0:
            result = AssitStudy.objects.filter(number=username,rangeCode=code)
            if len(result)>0:
                AssitStudy.objects.filter(number=username).update(rangeCode=0)

            id = str(id)
            if len(result)>0:
                pd = AssitStudy.objects.filter(number=username).values('password')
                password = (list(pd)[0])['password']
                user = authenticate(username=username, password=password)
                if user is not None:
                    login(request,user)
                    if id==str(1):
                        return HttpResponseRedirect('/main/')
                    elif id==str(2):
                        return HttpResponseRedirect('/stcred/')
                    elif id==str(3):
                        return HttpResponseRedirect('/course/')
                    elif id==str(4):
                        return HttpResponseRedirect('/inst/')
                    else:
                        return HttpResponseRedirect('/')
                else:
                    return HttpResponseRedirect('/')
            else:
                return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect('/')




#重新确定方向
class ReconfirmIterestView(View):
    def post(self,request):
        if request.user.is_authenticated:
            student_number = request.POST.get('student_number','')
            mychoice = request.POST.get('choice')
            MyMessage.objects.filter(st_id=student_number).update(favor=mychoice)
            json_data = {'message':'成功'}

            return JsonResponse(json_data)
        else:
            return HttpResponseRedirect('/')


#涉及技能
class AboutTc(View):
    def post(self,request):
        if request.user.is_authenticated:
            mychoice = request.POST.get('choice')

            type_id = Types.objects.filter(type_name=mychoice).values('id')
            tc = Technologys.objects.filter(type_name_id=(type_id[0])['id']).values('name')
            tc_List = ''
            for i in tc:
                tc_List+=i['name']+'\t'

            tc = HotJob.objects.filter(type_name_id=(type_id[0])['id']).values('title')
            job_List = ''
            for i in tc:
                job_List += i['title'] + '\t'


            json_data = {'tc':tc_List,'job':job_List}

            return JsonResponse(json_data)
        else:
            return HttpResponseRedirect('/')


#关联分析
class HpView(View):
    def get(self,request):
        file = AssociateGrade.objects.values_list('id','student_id','grade')
        borrow = AssociateBook.objects.values_list('student_id','number')
        minimum_score = 90
        table = {}
        for line in file:
            line = list(line)
            if int(line[-1]) >= minimum_score:
                if line[1] not in table:
                    table[line[1]] = 1
                else:
                    table[line[1]] += 1
        result = []
        for line in borrow:
            line = list(line)
            line1 = []
            if line[0] in table:
                line1.append(line[1])
                line1.append(table[line[0]])
            result.append(line1)
        data = {'datas':result}

        #籍贯-成绩
        borrow = Associateaward.objects.values_list('id','student_id')
        file = Associate_native_place.objects.values_list('id','student_id','jiguan')
        table, number = self.getdata(file)
        aq, n = self.assdd(table, borrow)
        natice_place = []
        percent = []
        for k, v in aq.items():
            a = k
            b = v / number[k] * 100
            natice_place.append(a)
            percent.append(round(b))
        native_place_data = {'natice_place':natice_place,'percent':percent}

        #学院-性别-成绩
        file1 = AssociateGender.objects.values_list('id', 'student_id', 'gender','collage')
        borrow1 = Associateaward.objects.values_list('id','student_id')
        table, number = self.getdata1(file1)
        aq, n = self.assdd1(table,borrow1)
        datas = []
        for k, v in aq.items():
            lst = []
            a = k[0]
            c = k[1]
            b = v / number[k[1]] * 100
            # print('{},{},{:.2f}%'.format(c, a, b))
            per_collage = []
            per_collage.append(c)
            per_collage.append(a)
            per_collage.append(b)
            datas.append(per_collage)
        datas.sort()
        collage = []
        male_percent = []
        famale_percent = []
        for col in datas:
            if col[0] not in collage:
                collage.append(col[0])
            if col[1] == '男':
                male_percent.append(round(col[2]))
            if col[1] == '女':
                famale_percent.append(round(col[2]))

        collage_datas = {'collage': collage, 'male_percent': male_percent, 'famale_percent': famale_percent}


        #课程-课程
        # ts = time.time()
        score = 70

        file2 = AssociateCourseGrade.objects.values_list('id','student_id','course_id','grade')
        source = AssociateCourse.objects.values_list('course_id','course_name')
        score_table = self.getdata2(file2, score)
        min_support = math.ceil(len(score_table) * 0.4)  # 计算最小支持数，向上取整
        min_confident = 0.6
        # print('Number of Student:', len(score_table))
        # print('Min_Support:', min_support)
        # print('Min_Confident:', min_confident)
        c1, L1, table2, l = self.genl1(score_table, min_support)
        all_ls = []  # 所有频繁项集是列表形式
        all_ls.append(l)  # 将1频繁项集添加到所有的频繁项集中 # TODO
        L = list(L1.keys())  # 部分， 用于生成hash
        C2 = self.hash_l2(table2, L, min_support)
        C2s = self.calc_supportX(C2, score_table)
        mark = self.gen_mark(C2s, L,min_support,all_ls)
        l_next = C2s
        while (len(l_next)):
            for mk, v in mark.items():
                mark[mk] = v - 1
            nd = self.next_gen(l_next, mark, min_support)
            l_next = nd
            mark = self.update_mark(mark)
            if len(l_next) > 0:
                all_ls.append(l_next)
                # print('l_%d length:' % len(all_ls), len(l_next))
                ## 生成k+1项集
                c_next = self.combinationsX(list(mark.keys()), len(all_ls) + 1)
                # print('%%%%', len(c_next))
                l_next = self.calc_supportX(c_next, table2)
        l = all_ls[-1]
        result = []
        for item in l:
            r = self.generate_rules(source, list(item), all_ls, l[item], min_confident)
            result.append(r)
        # print(time.time() - ts)

        # for j in result:
        #     for k in j:
                #print(k)
            # print('-------------------------')

        return render(request, 'stu/associated.html', {
            'data_borrow':json.dumps(data),
            'native_place_data':json.dumps(native_place_data)

        })

    def getdata(self,file):
        table = defaultdict(list)
        number = {}
        for line in file:
            if line[2] not in number:
                number[line[2]] = 1
            else:
                number[line[2]] += 1

            if line[1] not in table:
                table[line[0]].append(line[1])
                table[line[1]].append(line[2])
        for key in table:
            table[key].sort()
        return table, number

    def assdd(self,table, borrow):
        aq = {}
        n = 0
        for line in borrow:
            if line[1] in table:
                n += 1
                if table[line[1]][0] not in aq:
                    aq[table[line[1]][0]] = 1
                else:
                    aq[table[line[1]][0]] += 1
        return aq, n

    def getdata1(self,file):
        table = defaultdict(list)
        number = {}
        for line in file:
            if line[1] not in table:
                table[line[1]].append(line[2])
                table[line[1]].append(line[3])

            if line[3] not in number:
                number[line[3]] = 1
            else:
                number[line[3]] += 1
        return table, number

    def assdd1(self,table,borrow):
        aq = {}
        n = 0
        for line in borrow:
            if line[1] in table:
                n += 1
                if tuple(table[line[1]]) not in aq:
                    aq[tuple(table[line[1]])] = 1
                else:
                    aq[tuple(table[line[1]])] += 1
        return aq, n

    def getdata2(self,file, minimum_score):
        """
        读取csv文件的数据，并根据给定的分数值筛选符合要求的数据，并以字典的形式返回
        :param file_path: 数据文件的存放路径
        :param minimum_score: 符合要求的最低分数值
        :return: 返回table，table的key是学生的学号，每个key对应的value是该学生符合要求的课程
        """
        # with open(file_path) as f:
        #     f_csv = csv.reader(f)
        table = defaultdict(list)  # defaultdict是指字典

        for line in file:  # 读取的是成绩的excel表
            # print(line)
            if int(line[3]) >= minimum_score and line[2] not in table[line[1]]:
                table[line[1]].append(line[2])
        for key in table:
            table[key].sort()
        return table

    #往下是课程-课程
    def genl1(self,table, min_support):
        """
        产生频繁一项集
        :param table: 数据表
        :param min_support: 最小支持度
        :return: 返回频繁一项集:所有: c1; > min_support :l1
        """
        c1 = {}
        keys = []
        table2 = defaultdict(list)
        for stu in table:  # 学号在Table表
            for course in table[stu]:  # 课程在table表中
                if course in c1:
                    c1[course] += 1
                else:
                    keys.append(course)
                    c1[course] = 1
        keys.sort()
        l1 = {}
        l = {}  # TODO
        for key in keys:
            if c1[key] >= min_support:
                l1[key] = c1[key]
                l[(key,)] = c1[key]  # TODO
        # 新table
        for stu in table:
            for course in table[stu]:
                if course in l1:
                    table2[stu].append(course)
        return c1, l1, table2, l

    # ## hash 二项频繁集
    def combination2(self,t0):
        c2 = []
        for tti in range(len(t0)):
            c2.append(list(combinations(t0[tti], 2)))
        # print('c2',c2)     #相当于把所有的分解的数据库展开
        return c2

    def hash_l2(self,table2, L, min_support):
        t = []
        for key, value in table2.items():
            t.append(value)
        t2 = self.combination2(t)
        hashr = [0 for i in range(997)]
        hashbit = [0 for i in range(997)]
        for t2t1 in t2:
            for X in t2t1:
                hash1 = 10 * L.index(X[0]) + L.index(X[1])
                hash1 %= 997
                hashr[hash1] += 1
                if hashr[hash1] > min_support:
                    hashbit[hash1] = 1

        # hash 二项集生成
        L1L1 = list(combinations(L, 2))
        C2 = []
        for y in L1L1:
            hash2 = 10 * L.index(y[0]) + L.index(y[0])
            hash2 %= 997
            if hashbit[hash2] > 0:
                C2.append(y)
        # print('~~~~',len(C2))
        return C2

    # ## 计算二项集支持度
    def calc_supportX(self,C2, table2):
        C2s = {}
        for key in C2:  # 在候选项集中找项集
            for stu in table2:  # table表中的学号
                if set(key).issubset(table2[stu]):  # set(key)是否包含在table[stu]中
                    if key in C2s:
                        C2s[key] += 1
                    else:
                        C2s[key] = 1
        return C2s

    # ## 二项集mark计算
    def gen_mark(self,C2s, L,min_support,all_ls):
        mark = dict(zip(L, [0 for i in range(len(L))]))
        for key, value in C2s.items():
            if value >= min_support:
                for item in key:
                    cnfd = value / all_ls[0][(item,)]  # TODO
                    if cnfd > 0.5:
                        mark[item] += 1
        return mark

    # ## 循环生成多项集
    def next_gen(self,l_next, mark, min_support):
        nd = {}
        for keys, v in l_next.items():
            if v > min_support:
                temp = list(set(keys))
                flag = 1
                for i in range(len(temp)):
                    if mark[temp[i]] < 1:
                        flag = 0
                        break
                if flag:
                    nd[keys] = v
        return nd

    def combinationsX(self,l, t):
        C = []
        C_next = []
        for l in list(combinations(l, t)):
            if set(l) not in C:
                C.append(set(l))
                C_next.append(l)
        return C_next

    # 更新 mark
    def update_mark(self,mark):
        mark_s = {}
        for mk, v in mark.items():
            if v > 0:
                mark_s[mk] = v
        return mark_s

    # ## 关联规则生成
    def generate_rules(self,source, l, all_ls, support, min_confident):
        """
        关联规则生成算法
        :param l: 频繁项集
        :param all_ls: 所有的频繁项集，记录了每个频繁项集的支持度
        :param support: 频繁项集l的支持度
        :param min_confident: 最小置信度

        """
        course = {}
        # with open(source_path) as f:
        #     course_csv = csv.reader(f)
        for line in source:
            course[line[0]] = line[1]
        subsets = []
        length = len(l)
        # print('!!!!!!',length)
        for i in range(1, length):
            subsets.append(list(combinations(l, i)))
        result = []
        for subset in subsets:
            for item in subset:
                tmp = list(set(l) - set(item))
                tmp.sort()
                if item in all_ls[len(item) - 1]:  # TODO
                    cnfd = support / all_ls[len(item) - 1][item]
                    if cnfd >= min_confident:
                        per_result = []
                        a = [course[i] for i in item]
                        b = [course[i] for i in tmp]
                        # print(a, '-->', b, ' 置信度:', cnfd, sep='')
                        per_result.append(a)
                        per_result.append(b)
                        per_result.append(cnfd)
                        result.append(per_result)
        return result

    def has_infrequent_subset(self,c, l_pre):
        """
        根据Apriori算法的先验性质，进行剪枝处理
        :param c: 新生成的候选项K集中的某一项
        :param l_pre: 频繁(k-1)项集
        :return:
        """
        for item in c:  # item是频繁项集中的项
            tmpsubset = list(c - {item})  # tmpsnbset是指频繁项集中的课程代码项
            tmpsubset.sort()  # l_pre.keys()频繁项集，如：odict_keys([('c0103810',), ('c1103001',), ('c1104001',), ('c1106001',)])
            if not {tuple(tmpsubset)}.issubset(
                    set(l_pre.keys())):  # issubset() 方法用于判断集合的所有元素是否都包含在指定集合中，如果是则返回 True，否则返回 False
                return True  # tuple(tmpsubset)}是否包含在l_pre.keys()
        return False

    def apriori_gen(self,l_pre):
        """
        生成候选K项集
        :param l_pre: 频繁K-1项集
        :return: 候选K项集c_next
        """
        keys = list()
        l_pre_key_list = list(l_pre.keys())
        l_pre_key_list.sort()  # 1频繁项集课程代码进行排序
        for idx, item1 in enumerate(
                l_pre_key_list):  # enumerate() 函数用于将一个可遍历的数据对象(如列表、元组或字符串)组合为一个索引序列，同时列出数据和数据下标，一般用在 for 循环当中
            for i in range(idx + 1, len(l_pre_key_list)):  # 在idx+1和1频繁集的长度之间
                item2 = l_pre_key_list[i]
                if item1[:-1] == item2[:-1] and \
                        not self.has_infrequent_subset(set(item1) | set(item2), l_pre):  # has_infrequent_subset调用进行了剪枝
                    item = list(set(item1) | set(item2))
                    item.sort()  # 对项集进行排序
                    keys.append(item)  # keys添加项集
        c_next = OrderedDict((tuple(key), 0) for key in keys)  # OrderedDict,实现了对字典对象中元素的排序，产生C2
        return c_next



        # else:
            # return HttpResponseRedirect('/')


def page_not_found(request):
    #全局404
    from django.shortcuts import render_to_response
    response = render_to_response('others/404.html', {})
    response.status_code = 404
    return response


def page_error(request):
    #全局404
    from django.shortcuts import render_to_response
    response = render_to_response('others/500.html', {})
    response.status_code = 500
    return response


def page_reject(request):
    #全局404
    from django.shortcuts import render_to_response
    response = render_to_response('others/403.html', {})
    response.status_code = 403
    return response
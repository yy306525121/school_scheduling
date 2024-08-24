import pandas as pd
from ortools.sat.python import cp_model


# 排课
def plan(teacher_subjects, subjects_required, teacher_required={}):
    # 教师
    teachers_list = list(teacher_subjects.keys())

    # 班级数
    classes_list = list(subjects_required.keys())

    # 课程
    subjects_set = set()
    for subject_required in subjects_required.values():
        subjects_set.update(subject_required.keys())
    subjects_list = list(subjects_set)

    # 建模
    model = cp_model.CpModel()

    # 决策变量：教师i在班级j的第k天第l个课时教授课程m
    x = {}

    for teacher in teachers_list:
        for class_ in classes_list:
            for day in range(6):
                for period in range(9):
                    for subject in subjects_list:
                        x[teacher, class_, day, period, subject] = model.NewBoolVar(
                            f"x[{teacher}, {class_}, {day}, {period}, {subject}]"
                        )
    model.Add(x['郑成功', '高三1班', 3, 8, '体育'] == 1)

    # 辅助变量：是否和下一节课连续
    consecutive = {}
    for teacher in teachers_list:
        for class_ in classes_list:
            for day in range(6):
                for period in range(8):
                    for subject in subjects_list:
                        consecutive[teacher, class_, day, period, subject] = (
                            model.NewBoolVar(
                                f"consecutive[{teacher}, {class_}, {day}, {period}, {subject}]"
                            )
                        )

    # 辅助变量：135第一节是否上语文，246第一节是否上英语
    first_lesson_preferred = {}
    for class_ in classes_list:
        for day in range(6):
            first_lesson_preferred[class_, day] = model.NewBoolVar(f'first_lesson_preferred_{class_}_{day}')

    # 辅助变量：每个老师每天的最早课时
    teacher_earliest_period = {}
    for teacher in teachers_list:
        for day in range(6):
            teacher_earliest_period[teacher, day] = model.NewIntVar(0, 8, f'teacher_earliest_period_{teacher}_{day}')

    # 辅助变量：每个老师每天的最晚课时
    teacher_latest_period = {}
    for teacher in teachers_list:
        for day in range(6):
            teacher_latest_period[teacher, day] = model.NewIntVar(0, 8, f'teacher_latest_period_{teacher}_{day}')

    # 辅助变量：每个老师每天的课时差
    teacher_period_gap = {}
    for teacher in teachers_list:
        for day in range(6):
            teacher_period_gap[teacher, day] = model.NewIntVar(0, 8, f'teacher_period_gap_{teacher}_{day}')

    # 约束条件：指定老师
    for teacher in teachers_list:
        for class_ in classes_list:
            for subject in subjects_list:
                if teacher_required.get(class_, {}).get(subject) == teacher:
                    model.Add(
                        sum(
                            x[teacher, class_, day, period, subject]
                            for day in range(6)
                            for period in range(9)
                        ) >= 1
                    )

    # 约束条件：每个老师只教授自己的课
    for teacher in teachers_list:
        for class_ in classes_list:
            for day in range(6):
                for period in range(9):
                    for subject in subjects_list:
                        if subject not in teacher_subjects[teacher]:
                            model.Add(x[teacher, class_, day, period, subject] == 0)

    # 约束条件：每个班级有固定的课时数
    for class_ in classes_list:
        for subject in subjects_list:
            model.Add(
                sum(
                    x[teacher, class_, day, period, subject]
                    for teacher in teachers_list
                    for day in range(6)
                    for period in range(9)
                ) == subjects_required[class_].get(subject, 0)
            )

    # 约束条件：每个班同一个课程只能用一个老师
    for class_ in classes_list:
        for subject in subjects_list:

            # 对于每个班级和课程，创建一个辅助变量来表示哪个老师教授这门课
            teacher_indicator = {}
            for teacher in teachers_list:
                teacher_indicator[teacher] = model.NewBoolVar(
                    f"teacher_indicator[{teacher}, {class_}, {subject}]"
                )

            # 确保只有一个教师指示器为真
            model.Add(sum(teacher_indicator.values()) <= 1)

            for teacher in teachers_list:
                # 如果教师指示器为真，那么这个教师必须至少教一节这门课
                model.Add(
                    sum(
                        x[teacher, class_, day, period, subject]
                        for day in range(6)
                        for period in range(9)
                    ) >= teacher_indicator[teacher]
                )

                # 如果这个教师教了这门课，那么教师指示器必须为真
                for day in range(6):
                    for period in range(9):
                        model.Add(
                            x[teacher, class_, day, period, subject]
                            <= teacher_indicator[teacher]
                        )

    # 约束条件：每个老师每天在每个班最多教两节相同的课程，如果有两节相同的课程，课程必须连着上，并且不能在第5节和第6节
    for teacher in teachers_list:
        for class_ in classes_list:
            for day in range(6):
                for subject in subjects_list:
                    # 计算这门课在这一天的总课程数
                    total_lessons = sum(
                        x[teacher, class_, day, period, subject] for period in range(9)
                    )

                    # 1. 限制每天每个班级每门课最多两节
                    model.Add(total_lessons <= 2)

                    # 2. 如果有两节课，必须连续
                    # 创建变量，是否和下一节课连续
                    consecutive_sum = sum(
                        consecutive[teacher, class_, day, period, subject]
                        for period in range(8)
                    )

                    # 2 节课，consecutive_sum 为 1
                    # 1 节课，consecutive_sum 为 0
                    # 0 节课，consecutive_sum 为 0
                    model.Add(consecutive_sum >= total_lessons - 1)

                    # 连续性约束
                    for period in range(8):
                        # 连续性为真时，两节课都为真
                        model.AddBoolAnd(
                            [
                                x[teacher, class_, day, period, subject],
                                x[teacher, class_, day, period + 1, subject],
                            ]
                        ).OnlyEnforceIf(
                            consecutive[teacher, class_, day, period, subject]
                        )
                        # 连续性为假时，至少有一节为假
                        model.AddBoolOr(
                            [
                                x[teacher, class_, day, period, subject].Not(),
                                x[teacher, class_, day, period + 1, subject].Not(),
                            ]
                        ).OnlyEnforceIf(
                            consecutive[teacher, class_, day, period, subject].Not()
                        )

                    # 3. 不能在第5节和第6节安排连续的两节课
                    model.Add(x[teacher, class_, day, 4, subject] + x[teacher, class_, day, 5, subject] <= 1)

    # 约束条件：每个老师在每天相同时段只能出现一次
    for teacher in teachers_list:
        for day in range(6):
            for period in range(9):
                model.Add(
                    sum(
                        x[teacher, class_, day, period, subject]
                        for class_ in classes_list
                        for subject in subjects_list
                    ) <= 1
                )

    # 约束条件：每个班级同天相同时段只能有一个课
    for class_ in classes_list:
        for day in range(6):
            for period in range(9):
                model.Add(
                    sum(
                        x[teacher, class_, day, period, subject]
                        for teacher in teachers_list
                        for subject in subjects_list
                    ) <= 1
                )

    # 添加软约束：135第一节尽可能上语文，246第一节尽可能上英语
    for class_ in classes_list:
        for day in range(6):
            if day % 2 == 0:  # 135 (对应 0, 2, 4)
                model.Add(sum(x[teacher, class_, day, 0, '语文'] for teacher in teachers_list) == 1).OnlyEnforceIf(first_lesson_preferred[class_, day])
            else:  # 246 (对应 1, 3, 5)
                model.Add(sum(x[teacher, class_, day, 0, '英语'] for teacher in teachers_list) == 1).OnlyEnforceIf(first_lesson_preferred[class_, day])

    # 约束条件：体育课不能排上午前 2 节
    for teacher in teachers_list:
        for class_ in classes_list:
            for day in range(6):
                for period in range(2):  # 前两节课
                    model.Add(x[teacher, class_, day, period, '体育'] == 0)

    # 约束条件：体育课只能排在周 456
    for teacher in teachers_list:
        for class_ in classes_list:
            for day in range(3):  # 周一、二、三
                for period in range(9):
                    model.Add(x[teacher, class_, day, period, '体育'] == 0)

    # 约束条件：第一节、第二节和第六节必须排课
    for class_ in classes_list:
        for day in range(6):
            for period in [0, 1, 5]:  # 第一节、第二节和第六节
                model.Add(sum(x[teacher, class_, day, period, subject] 
                            for teacher in teachers_list 
                            for subject in subjects_list) == 1)

    # 连课最小值，需求课时数 - 6 求和
    min_consecutive = 0
    for class_ in subjects_required:
        for subject in subjects_required[class_]:
            min_consecutive += max(0, subjects_required[class_][subject] - 6)

    # 约束条件：连课最小值
    model.Add(sum(consecutive.values()) == min_consecutive)

    # 添加约束：计算每个老师每天的最早和最晚课时
    for teacher in teachers_list:
        for day in range(6):
            # 创建辅助变量，表示老师在某一时段是否有课
            has_class = {}
            for period in range(9):
                has_class[period] = model.NewBoolVar(f'has_class_{teacher}_{day}_{period}')
                model.Add(sum(x[teacher, class_, day, period, subject] 
                            for class_ in classes_list 
                            for subject in subjects_list) == 1).OnlyEnforceIf(has_class[period])
                model.Add(sum(x[teacher, class_, day, period, subject] 
                            for class_ in classes_list 
                            for subject in subjects_list) == 0).OnlyEnforceIf(has_class[period].Not())

            # 最早课时
            model.AddMinEquality(teacher_earliest_period[teacher, day], 
                                [period * has_class[period] for period in range(9)])

            # 最晚课时
            model.AddMaxEquality(teacher_latest_period[teacher, day], 
                                [period * has_class[period] for period in range(9)])

    # 添加约束：计算每个老师每天的课时差
    for teacher in teachers_list:
        for day in range(6):
            model.Add(teacher_period_gap[teacher, day] == 
                    teacher_latest_period[teacher, day] - teacher_earliest_period[teacher, day])

    # 目标函数：135语文 246英语，每个老师同一天所有课的课时差最小
    model.Maximize(sum(first_lesson_preferred.values()) * 10000 - sum(teacher_period_gap.values()))

    # 求解
    solver = cp_model.CpSolver()

    # 使用的线程数
    # solver.parameters.num_search_workers = 1

    # 限制求解时间
    solver.parameters.max_time_in_seconds = 600

    # 开启搜索进度
    solver.parameters.log_search_progress = True

    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # 求解结果状态
        if status == cp_model.OPTIMAL:
            print("Optimal solution")
        else:
            print("Feasible solution")

        # 求解结果
        df_dict = {}

        # 创建星期和课时
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六"]
        periods = ["第一节", "第二节", "第三节", "第四节", "第五节", "第六节", "第七节", "第八节", "第九节",]

        # 为每个班级创建一个 df
        for class_ in classes_list:
            df_dict[class_] = pd.DataFrame(index=periods, columns=weekdays)

        # 解析结果
        for teacher in teachers_list:
            for class_ in classes_list:
                for day in range(6):
                    for period in range(9):
                        for subject in subjects_list:
                            if (solver.Value(x[teacher, class_, day, period, subject]) == 1):
                                df_dict[class_].loc[periods[period], weekdays[day]] = f"{subject}（{teacher}）"

        # 处理结果，每个 df 一个 sheet
        with pd.ExcelWriter("排课结果.xlsx") as writer:
            # 将每个DataFrame写入不同的sheet
            for class_, df in df_dict.items():
                df.to_excel(writer, sheet_name=class_)

    else:
        print("No optimal solution found.")




def main():
    # 教师技能字典：
    teacher_subjects = {
        "叮铃铃": ["化学"],
        "代驾": ["历史"],
        "何萌萌": ["语文"],
        "余利群": ["历史"],
        "余响": ["地理"],
        "冯新新": ["地理"],
        "大妹妹": ["数学"],
        "叶真": ["英语"],
        "马家家": ["数学"],
        "周钱": ["数学"],
        "周无敌": ["地理"],
        "礼炮": ["英语"],
        "大奔": ["化学"],
        "周五六": ["生物"],
        "小朋": ["生物"],
        "小李": ["语文"],
        "小王": ["历史"],
        "李四": ["物理"],
        "王五": ["物理", "信息技术"],
        "赵六": ["数学"],
        "曾书书": ["物理"],
        "张三峰": ["地理"],
        "张无忌": ["英语"],
        "李师太": ["地理"],
        "徐大侠": ["物理"],
        "张小凡": ["美术"],
        "金瓶儿": ["数学"],
        "碧瑶": ["英语"],
        "鬼王": ["生物"],
        "幽姨": ["日语"],
        "张宝": ["音乐"],
        "孙悟空": ["生物"],
        "猪八戒": ["政治"],
        "沙僧": ["语文"],
        "唐僧": ["物理"],
        "观音": ["历史"],
        "玉帝": ["语文"],
        "大师兄": ["政治"],
        "小师妹": ["数学"],
        "王林": ["英语"],
        "藤化元": ["语文"],
        "藤一": ["化学"],
        "藤二": ["历史"],
        "藤三": ["历史"],
        "藤四": ["政治"],
        "藤五": ["政治"],
        "藤六": ["语文"],
        "羽化门": ["语文"],
        "青阳门": ["语文"],
        "焚香谷": ["数学"],
        "天音寺": ["政治"],
        "郑成功": ["体育"],
        "郭襄": ["政治"],
        "阎王": ["化学"],
        "牛头": ["地理"],
        "马面": ["生物"],
        "至尊宝": ["语文"],
        "陈真": ["语文"],
        "李世民": ["英语"],
        "杨辉": ["数学"],
        "袁天罡": ["数学"],
        "李星云": ["英语"],
        "李茂贞": ["数学"],
    }

    # 班级技能需求量
    subjects_required = {
        "高三1班": {
            "语文": 8,
            "数学": 9,
            "英语": 8,
            "物理": 9,
            "化学": 8,
            "生物": 7,
            "体育": 1,
        },
        "高三2班": {
            "语文": 8,
            "数学": 9,
            "英语": 8,
            "政治": 8,
            "历史": 8,
            "地理": 8,
            "体育": 1,
        },
        "高三3班": {
            "语文": 8,
            "数学": 9,
            "英语": 8,
            "政治": 8,
            "历史": 8,
            "地理": 8,
            "体育": 1,
        },
    }

    # 指定老师
    teacher_required = {
        "高三1班": {
            "语文": "玉帝",
            "数学": "杨辉",
            "英语": "碧瑶",
            "物理": "李四",
            "化学": "阎王",
            "生物": "马面",
            "体育": "郑成功",
        },
        "高三2班": {
            "语文": "玉帝",
            "数学": "杨辉",
            "英语": "李星云",
            "政治": "天音寺",
            "历史": "观音",
            "地理": "冯新新",
            "体育": "郑成功",
        },
        "高三3班": {
            "语文": "至尊宝",
            "数学": "马家家",
            "英语": "李星云",
            "政治": "藤四",
            "历史": "余利群",
            "地理": "冯新新",
            "体育": "郑成功",
        },
    }

    # 求解
    plan(teacher_subjects, subjects_required, teacher_required)


if __name__ == "__main__":
    main()

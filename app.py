from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
import time
import threading
import uuid
import extract

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# 用户数据库
users = {}

# 课程数据结构
extract.readpdf()

# 用户选课数据
user_courses = {}  # 格式: {username: {course_name: [course_id1, ...]}}

# 抢课方案存储
plan_storage = {}

# 抢课任务状态
execution_status = {}


@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    user_selected = user_courses.get(username, {})
    courses = extract.usercourses(username)
    # 按学科分类组织所有课程
    courses_by_subject = {}
    for course in courses.values():
        subject = course['subject']
        if subject not in courses_by_subject:
            courses_by_subject[subject] = {}

        # 按课程名称分组
        course_name = course['name']
        if course_name not in courses_by_subject[subject]:
            courses_by_subject[subject][course_name] = []

        courses_by_subject[subject][course_name].append(course)

    # 获取用户已选课程（按课程名称分组）
    selected_by_subject = {}
    for course_name, course_ids in user_selected.items():
        for course_id in course_ids:
            course = courses.get(course_id)
            if course:
                subject = course['subject']
                if subject not in selected_by_subject:
                    selected_by_subject[subject] = {}

                if course_name not in selected_by_subject[subject]:
                    selected_by_subject[subject][course_name] = []

                selected_by_subject[subject][course_name].append(course)

    return render_template('home.html',
                           username=username,
                           courses_by_subject=courses_by_subject,
                           selected_by_subject=selected_by_subject,
                           user_selected=user_selected)


@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def handle_login():
    username = request.form['username']
    password = request.form['password']

    # 自动注册逻辑
    if username not in users:
        users[username] = password  # 实际应用中应加密存储
        user_courses[username] = {}  # 初始化用户课程
        flash('账号已自动创建，请牢记密码！')

    # 验证密码
    if users[username] == password:
        session['username'] = username
        return redirect(url_for('index'))
    else:
        flash('密码错误，请重试！')
        return redirect(url_for('login'))


@app.route('/grab_course', methods=['POST'])
def grab_course():
    if 'username' not in session:
        return jsonify(success=False, message="请先登录")

    username = session['username']
    course_id = request.form.get('course_id')
    courses = extract.usercourses(username)

    try:
        course_id = int(course_id)
    except (TypeError, ValueError):
        return jsonify(success=False, message="无效的课程ID")

    # 检查课程是否存在
    if course_id not in courses:
        return jsonify(success=False, message="课程不存在")

    course = courses[course_id]
    course_name = course['name']

    # 检查用户是否已选择同一课程的其他时段
    user_selected = user_courses.get(username, {})
    if course_name in user_selected:
        # 用户已经选择了该课程的其他时段
        return jsonify(success=False, message=f"您已选择{course_name}的其他时段")

    # 检查名额是否足够
    if course['remaining'] <= 0:
        return jsonify(success=False, message="课程名额已满")

    # 抢课
    if username not in user_courses:
        user_courses[username] = {}

    if course_name not in user_courses[username]:
        user_courses[username][course_name] = []

    user_courses[username][course_name].append(course_id)
    course['remaining'] -= 1

    return jsonify(success=True,
                   message=f"抢课成功！已选择{course_name}（{course['teacher']}教授）",
                   selected_course=course,
                   remaining=course['remaining'])


@app.route('/drop_course', methods=['POST'])
def drop_course():
    if 'username' not in session:
        return jsonify(success=False, message="请先登录")

    username = session['username']
    course_id = request.form.get('course_id')
    courses = extract.usercourses(username)

    try:
        course_id = int(course_id)
    except (TypeError, ValueError):
        return jsonify(success=False, message="无效的课程ID")

    # 检查课程是否存在
    if course_id not in courses:
        return jsonify(success=False, message="课程不存在")

    course = courses[course_id]
    course_name = course['name']

    # 检查用户是否选择了该课程
    if username not in user_courses or course_name not in user_courses[username]:
        return jsonify(success=False, message="您未选择该课程")

    # 检查用户是否选择了该特定课程实例
    if course_id not in user_courses[username][course_name]:
        return jsonify(success=False, message="您未选择该课程的这个时段")

    # 退选
    user_courses[username][course_name].remove(course_id)

    # 如果该课程名称下没有其他课程了，删除整个课程名称条目
    if not user_courses[username][course_name]:
        del user_courses[username][course_name]

    # 如果用户没有选择任何课程了，删除整个用户条目
    if not user_courses[username]:
        del user_courses[username]

    course['remaining'] += 1

    return jsonify(success=True,
                   message=f"退选成功！已取消{course_name}（{course['teacher']}教授）",
                   remaining=course['remaining'])


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


# 抢课辅助功能路由
@app.route('/save_plan', methods=['POST'])
def save_plan():
    if 'username' not in session:
        return jsonify(success=False, message='未登录', code=401)

    username = session['username']
    data = request.json
    plan_name = data.get('name')
    course_ids = data.get('courses', [])
    courses = extract.usercourses(username)

    # 验证方案名称
    if not plan_name or not plan_name.strip():
        return jsonify(success=False, message='方案名称不能为空', code=400)

    plan_name = plan_name.strip()

    # 处理删除方案的情况（空课程列表）
    if not course_ids:  # 空数组表示删除方案
        # 检查方案是否存在（不区分大小写）
        if username in plan_storage:
            # 查找方案（不区分大小写）
            matching_plans = [name for name in plan_storage[username].keys()
                              if name.lower() == plan_name.lower()]

            if matching_plans:
                actual_plan_name = matching_plans[0]
                del plan_storage[username][actual_plan_name]

                # 如果用户没有其他方案，删除整个用户条目
                if not plan_storage[username]:
                    del plan_storage[username]

                return jsonify(
                    success=True,
                    message=f'方案 "{actual_plan_name}" 已删除',
                    plan_name=actual_plan_name,
                    code=200
                )
            else:
                # 提供更详细的错误信息
                user_plans = list(plan_storage.get(username, {}).keys())
                return jsonify(
                    success=False,
                    message=f'方案 "{plan_name}" 不存在',
                    available_plans=user_plans,
                    code=404
                )
        else:
            return jsonify(
                success=False,
                message=f'方案 "{plan_name}" 不存在，您尚未创建任何方案',
                code=404
            )

    # 验证课程ID列表
    if not isinstance(course_ids, list):
        return jsonify(success=False, message='课程数据格式错误', code=400)

    # 验证和转换课程ID
    valid_course_ids = []
    invalid_course_ids = []

    for cid in course_ids:
        try:
            # 确保课程ID是整数
            course_id = int(cid)

            # 验证课程是否存在
            if course_id in courses:
                # 检查课程是否还有名额
                course = courses[course_id]
                if course['remaining'] <= 0:
                    invalid_course_ids.append(f"{course_id}(名额已满)")
                else:
                    valid_course_ids.append(course_id)
            else:
                invalid_course_ids.append(f"{cid}(课程不存在)")
        except (TypeError, ValueError):
            invalid_course_ids.append(f"{cid}(无效ID)")

    # 记录无效课程ID
    if invalid_course_ids:
        app.logger.warning(f"用户 {username} 尝试保存无效课程ID: {', '.join(invalid_course_ids)}")

    # 检查是否有有效的课程
    if not valid_course_ids:
        return jsonify(
            success=False,
            message='所选课程均无效',
            invalid_courses=invalid_course_ids,
            code=400
        )

    # 保存/更新方案（确保方案名称唯一且不区分大小写）
    if username not in plan_storage:
        plan_storage[username] = {}

    # 检查是否已有同名方案（不区分大小写）
    existing_plans = [name for name in plan_storage[username].keys()
                      if name.lower() == plan_name.lower()]

    if existing_plans:
        # 更新现有方案
        actual_plan_name = existing_plans[0]
        plan_storage[username][actual_plan_name] = valid_course_ids
        message = f'方案 "{actual_plan_name}" 已更新'
    else:
        # 添加新方案
        plan_storage[username][plan_name] = valid_course_ids
        message = f'方案 "{plan_name}" 已保存'

    # 返回成功响应（包含无效课程信息）
    response = {
        'success': True,
        'message': message,
        'plan_name': plan_name if not existing_plans else actual_plan_name,
        'valid_courses': valid_course_ids,
        'code': 200
    }

    if invalid_course_ids:
        response['warning'] = f'部分课程无效: {", ".join(invalid_course_ids)}'

    return jsonify(response)
@app.route('/get_plans', methods=['GET'])
def get_plans():
    if 'username' not in session:
        return jsonify(success=False, message='未登录', plans={})

    username = session['username']
    plans = plan_storage.get(username, {})
    return jsonify(success=True, plans=plans)


@app.route('/execute_plans', methods=['POST'])
def execute_plans():
    if 'username' not in session:
        return jsonify(success=False, message='未登录')

    username = session['username']
    plans = request.json.get('plans', [])

    if not plans:
        return jsonify(success=False, message='请选择至少一个方案')

    # 创建执行任务
    execution_id = str(uuid.uuid4())
    execution_status[execution_id] = {
        'status': 'running',
        'progress': 0,
        'results': [],
        'current_plan': None
    }

    # 在后台线程中执行抢课
    threading.Thread(target=execute_plans_thread, args=(username, plans, execution_id)).start()

    return jsonify(success=True, execution_id=execution_id)


def execute_plans_thread(username, plans, execution_id):
    """在后台线程中执行抢课方案"""
    status = execution_status[execution_id]
    total_plans = len(plans)

    for i, plan_name in enumerate(plans):
        status['current_plan'] = plan_name
        status['results'].append({'plan': plan_name, 'courses': []})

        if username in plan_storage and plan_name in plan_storage[username]:
            course_ids = plan_storage[username][plan_name]
            courses = extract.usercourses(username)
            for course_id in course_ids:
                # 检查课程是否存在
                if course_id not in courses:
                    status['results'][-1]['courses'].append({
                        'id': course_id,
                        'name': f"课程ID:{course_id}",
                        'status': 'failed',
                        'message': '课程不存在'
                    })
                    continue

                course = courses[course_id]
                # 添加课程信息到状态
                status['results'][-1]['courses'].append({
                    'id': course_id,
                    'name': course['name'],
                    'status': 'pending',
                    'message': '等待处理'
                })

                # 更新状态
                time.sleep(0.5)  # 模拟网络延迟

                # 检查课程是否可选
                if course['remaining'] <= 0:
                    status['results'][-1]['courses'][-1]['status'] = 'failed'
                    status['results'][-1]['courses'][-1]['message'] = '课程已满'
                    continue

                # 检查用户是否已选该课程的其他时段
                if username in user_courses and course['name'] in user_courses[username]:
                    status['results'][-1]['courses'][-1]['status'] = 'failed'
                    status['results'][-1]['courses'][-1]['message'] = '已选该课程其他时段'
                    continue

                # 执行选课
                if username not in user_courses:
                    user_courses[username] = {}
                if course['name'] not in user_courses[username]:
                    user_courses[username][course['name']] = []

                # 检查是否已经选了这个课程实例
                if course_id in user_courses[username][course['name']]:
                    status['results'][-1]['courses'][-1]['status'] = 'failed'
                    status['results'][-1]['courses'][-1]['message'] = '您已选择该课程'
                    continue

                # 执行选课
                user_courses[username][course['name']].append(course_id)
                course['remaining'] -= 1

                status['results'][-1]['courses'][-1]['status'] = 'success'
                status['results'][-1]['courses'][-1]['message'] = '选课成功'
                break  # 成功选择一门课后跳出当前方案
            else:
                # 如果该方案所有课程都尝试失败
                status['results'][-1]['message'] = '该方案所有课程均未成功'
        else:
            status['results'][-1]['message'] = '方案不存在'

        # 更新进度
        status['progress'] = ((i + 1) / total_plans) * 100

    status['status'] = 'completed'
    status['current_plan'] = None


@app.route('/execution_status/<execution_id>', methods=['GET'])
def get_execution_status(execution_id):
    if execution_id not in execution_status:
        return jsonify(success=False, message='执行ID无效')

    return jsonify(success=True, status=execution_status[execution_id])


if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0',port=5000)

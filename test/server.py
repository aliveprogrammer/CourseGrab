from flask import Flask, request, jsonify, redirect, url_for
from os import path
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def hello_world():
    return request.args.__str__()
usermap={}
@app.route('/register',methods=['POST'])
def register():
    print(request.headers)
    print(request.form)
    usermap[request.form['name']]=request.form['password']
    return "welcome "+request.form["name"]
@app.route('/login',methods=['POST'])
def login():
    if usermap.get(request.form['name'], '')==request.form['password']:
        return "successful login "+request.form["name"]
    else:
        return "unsuccessful login "+request.form["name"]

@app.route('/update',methods=['POST'])
def update():
    req=request.get_json()
    print(req)
    for user,pwd in req.items():
        if user in usermap:
            usermap[user]=pwd
    return jsonify(usermap)

@app.route('/upload/<ftype>',methods=['POST'])
def upload(ftype):
    pdf=request.files.get(ftype)
    print(type(pdf))
    pdf.save(path.join(".",app.config['UPLOAD_FOLDER'],"get."+ftype))
    return "successful upload "+pdf.filename

@app.route('/test1')
def test1():
    return redirect(url_for('test2'))

@app.route('/test2')
def test2():
    return 'this is test2'

if __name__ == '__main__':
    app.run(debug=True)
import requests

data={"name":"terry","password":"terry20080309"}
print(requests.post(url="http://127.0.0.1:5000/register",data=data).text)
print(requests.post(url="http://127.0.0.1:5000/login",data=data).text)
update={"terry":"Terry20080309","Ben":"bensonandben"}
r=requests.post(url="http://127.0.0.1:5000/update",json=update)
print(r.headers)
print(r.text)
up=open("../一些思路.docx","rb")
r=requests.post(url="http://127.0.0.1:5000/upload/docx",files={"docx":up})

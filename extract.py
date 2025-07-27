import pdfplumber

listofcourses = []
def solve(c,cm):
    places = c.pop(0)
    classrooms = []
    padding = {'405': '\n地理', '411': '\n物理', '410': '\n生物'}
    places = [i + padding.get(i, '') for i in places]
    for i in range(0, len(c), 2):
        time = c[i][1]
        for index, (name, teacher) in enumerate(zip(c[i], c[i + 1])):
            if teacher is None or teacher == '':
                continue
            p, subject = places[index].splitlines()
            classrooms.append({"name": subject + name[2], "teacher": teacher, "location": p, "time": time})

    courses = {}
    for id, d in enumerate(classrooms, 1):
        d.update(cm[d['name']])
        d.update({'id': id, 'capacity': 25, 'remaining': 25})
        courses[id] = d
    return courses

def readpdf():
    with pdfplumber.open('sample.pdf') as pdf:
        content,c1=pdf.pages[0].extract_tables()
        c2,c3=pdf.pages[1].extract_tables()

    content.pop(0)
    contentmap={}
    for subject,_,description in content:
        i=0
        for d in description.splitlines():
            if d.startswith("主题"):
                i+=1
                contentmap[subject+str(i)]={"subject":subject,'description':d}
            else:
                contentmap[subject+str(i)]['description']+=d
    global listofcourses
    listofcourses=[solve(p, contentmap) for p in (c2, c1, c3)]

def usercourses(username):
    return listofcourses[int(username[1:3])//4]

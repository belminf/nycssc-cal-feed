Scrapes NYC Social's EZFacility schedule webpage and creates calendar feed. Would probably work with other EZFacility leagues with minor modifications. Would also have to consider the timezone logic. May make it configurable at some point.

Requires some system packages:
```
yum install -y libxml-devel libxslt-devel python-virtualenv python-pip 
```

Create a virtualenv:
```
virtualenv --no-site-packages nycssc-cal
```

Install python requirements
```
pip install -r requirements.txt
```

Finally, add a cronjob to run `script.py`.

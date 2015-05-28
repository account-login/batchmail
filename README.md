This module contains utilities to sending photos, files by email.

# usage

```python
images = glob('*.JPG')
# sort and split images into groups
grps = files2groups(images, max_size=10*1024*1024, ordered_by='image.date')
# setup each Email instance
emls = groups2Emails(grps, title='Some photos')
for eml in emls:
    eml.from_ = 'xxx@example.com'
    eml.to = ['yyy@abc.com']
    eml.user_name = 'xxx@example.com'
    eml.password = '*********'
    eml.smtp = 'smtp.example.com'
    # send the email
    eml.send()
```
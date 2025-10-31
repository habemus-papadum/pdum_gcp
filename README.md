# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/habemus-papadum/pdum_gcp/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                         |    Stmts |     Miss |   Cover |   Missing |
|----------------------------- | -------: | -------: | ------: | --------: |
| src/pdum/gcp/\_\_init\_\_.py |        4 |        0 |    100% |           |
| src/pdum/gcp/\_clients.py    |       13 |        5 |     62% |16, 21, 26, 31, 36 |
| src/pdum/gcp/\_helpers.py    |       42 |       38 |     10% |29-38, 50-99 |
| src/pdum/gcp/admin.py        |      202 |      142 |     30% |62-96, 117-145, 178-219, 257-270, 303-311, 342, 417, 435-437, 450, 454, 481-482, 508-509, 527-624 |
| src/pdum/gcp/types.py        |      530 |      372 |     30% |102-105, 133, 153, 173, 193, 215, 232-235, 285-354, 387-398, 426-440, 452-478, 519-547, 592, 607-629, 644-659, 681-707, 752-789, 815, 848-879, 903-914, 955-975, 990-1012, 1027-1042, 1064-1090, 1127, 1153-1178, 1220-1276, 1305-1332, 1366-1375, 1405-1419, 1429-1437, 1465-1507, 1591-1594, 1628-1662, 1684, 1844-1865, 1878, 1914-1945 |
|                    **TOTAL** |  **791** |  **557** | **30%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/habemus-papadum/pdum_gcp/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/habemus-papadum/pdum_gcp/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/habemus-papadum/pdum_gcp/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/habemus-papadum/pdum_gcp/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fhabemus-papadum%2Fpdum_gcp%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/habemus-papadum/pdum_gcp/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.
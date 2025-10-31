# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/habemus-papadum/pdum_gcp/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                         |    Stmts |     Miss |   Cover |   Missing |
|----------------------------- | -------: | -------: | ------: | --------: |
| src/pdum/gcp/\_\_init\_\_.py |        4 |        0 |    100% |           |
| src/pdum/gcp/\_clients.py    |       13 |        5 |     62% |16, 21, 26, 31, 36 |
| src/pdum/gcp/\_helpers.py    |       42 |       38 |     10% |29-38, 50-99 |
| src/pdum/gcp/admin.py        |      202 |      142 |     30% |62-98, 115-143, 176-219, 257-270, 303-311, 342, 419, 440-442, 457, 461, 488-489, 515-516, 536-635 |
| src/pdum/gcp/types.py        |      530 |      372 |     30% |94-97, 120, 134, 148, 162, 177, 190-192, 242-315, 346-357, 385-399, 408-434, 475-503, 540, 555-579, 594-613, 635-663, 710-749, 775, 808-843, 867-878, 909-929, 944-968, 983-1002, 1024-1052, 1082, 1108-1135, 1177-1242, 1271-1300, 1334-1343, 1373-1387, 1397-1405, 1433-1475, 1556-1558, 1592-1630, 1645, 1780-1803, 1814, 1843-1876 |
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
# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/habemus-papadum/pdum_gcp/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                   |    Stmts |     Miss |   Cover |   Missing |
|--------------------------------------- | -------: | -------: | ------: | --------: |
| src/pdum/gcp/\_\_init\_\_.py           |        4 |        0 |    100% |           |
| src/pdum/gcp/\_clients.py              |       16 |        6 |     62% |17, 22, 27, 32, 37, 42 |
| src/pdum/gcp/\_helpers.py              |       42 |       38 |     10% |29-38, 50-99 |
| src/pdum/gcp/admin.py                  |      202 |      142 |     30% |62-96, 117-145, 178-219, 257-270, 303-311, 342, 417, 435-437, 450, 454, 481-482, 508-509, 527-624 |
| src/pdum/gcp/types/\_\_init\_\_.py     |       13 |        0 |    100% |           |
| src/pdum/gcp/types/billing\_account.py |       24 |        0 |    100% |           |
| src/pdum/gcp/types/constants.py        |        3 |        0 |    100% |           |
| src/pdum/gcp/types/container.py        |      123 |       92 |     25% |47, 67, 87, 107, 129, 151-152, 201-264, 286-294, 298-310, 314-336, 363, 374-389 |
| src/pdum/gcp/types/exceptions.py       |        4 |        0 |    100% |           |
| src/pdum/gcp/types/folder.py           |       57 |       44 |     23% |24-46, 50-71, 75-90, 94-110 |
| src/pdum/gcp/types/no\_org.py          |       61 |       30 |     51% |66-85, 89, 93-115 |
| src/pdum/gcp/types/organization.py     |      105 |       85 |     19% |40, 44-67, 71-86, 90-111, 127-164, 168, 181-205, 210-217 |
| src/pdum/gcp/types/project.py          |      207 |      150 |     28% |39, 43-60, 72-112, 116-135, 147-155, 173, 188-201, 212-220, 225-261, 304-307, 319-354, 358-361, 398-423, 428-430, 439 |
| src/pdum/gcp/types/region.py           |       96 |       17 |     82% |65, 71, 77, 83-87, 123, 129, 135, 141, 147-151 |
| src/pdum/gcp/types/resource.py         |       17 |        4 |     76% |     25-28 |
| src/pdum/gcp/types/role.py             |        8 |        0 |    100% |           |
|                              **TOTAL** |  **982** |  **608** | **38%** |           |


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
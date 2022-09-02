# pypedal

## Install and run

use

```sh
pip install .

# if production
uvicorn --no-use-colors pypedal.main:app

# if development
pip install .[dev,tests]
uvicorn --reload --no-use-colors pypedal.main:app

# use cli and get help
pypedal --help
pypedal slowed-reverb [youtube-link]
```

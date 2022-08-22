# Pyd-Pedal

## Install and run

use

```sh
pip install .

# if production
uvicorn --no-use-colors pypedal.main:app

# if development
pip install .[dev,tests]
uvicorn --reload --no-use-colors pypedal.main:app
```

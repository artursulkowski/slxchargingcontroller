# Development environment
How I setup my development environment.

## Get the code!
### Download homeassistant core

[HomeAssistant Core](https://github.com/home-assistant/core)
```bash
git git@github.com:home-assistant/core.git
```

Checkout the last stable version (I avoid work on dev version), e.g.:
```bash
cd core
git checkout 2024.8.0
```

### Add 3rd party custom integrations which I am using

[OpenEVSE](https://github.com/firstof9/openevse)
In the same directory which includes `core` run
```bash
git clone git@github.com:firstof9/openevse.git
cp -r ./openevse/custom_components/openevse ./core/config/custom_components
```

[kia_uvo](https://github.com/Hyundai-Kia-Connect/kia_uvo)
In the same directory which includes `core` run
```bash
git clone git@github.com:Hyundai-Kia-Connect/kia_uvo.git
cp -r ./kia_uvo/custom_components/kia_uvo ./core/config/custom_components
 ```

## Add slxcharging controller
```bash
cd core/config/custom_components
git clone git@github.com:artursulkowski/slxchargingcontroller.git
```

### Running slxcharging controller tests
Tests are run from `config/custom_components/slxchargingcontroller` using `pytest`

Before run, you need to make few tweaks:

**Add `__init__.py` into `custom_components` directory**
```bash
custom_components % cat __init__.py
"""Placeholder for tests. """
```

**Add current directory as correct path for python modules**
```diff
diff --git a/pyproject.toml b/pyproject.toml
index dc943b0832..20523a0bc1 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -435,6 +435,10 @@ max-line-length-suggestions = 72
 [tool.pytest.ini_options]
 testpaths = [
     "tests",
 ]
+
+pythonpath = [
+    ".",
+]

```

**Install manually pytest_homeassistant_custom_component**

Note: this can be moved to requirements.txt
``` bash
pip install pytest_homeassistant_custom_component
```

Mark custom_components as a module for slxcharging controller tests - crea

## Efficient debugging
### Disable generating translation when running HA in debug mode

`.vscode/launch.json`
```diff
   "configurations": [
     {
       "name": "Home Assistant",
       "type": "python",
       "module": "homeassistant",
       "justMyCode": false,
       "args": ["--debug", "-c", "config"],
-      "preLaunchTask": "Compile English translations"
+      //"preLaunchTask": "Compile English translations"
     },
```

### slxcharging controller pytests with debugger
`.vscode/launch.json`
```diff
   "configurations": [
    ...
+    {
+      "name": "Home Assistant: Changed tests SLX",
+      "type": "python",
+      "request": "launch",
+      "module": "pytest",
+      "justMyCode": false,
+      "args": ["--timeout=10", "config/custom_components/slxchargingcontroller/tests"],
+    },
```






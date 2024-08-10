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

### Add slxcharging controller
```bash
cd core/config/custom_components
git clone git@github.com:artursulkowski/slxchargingcontroller.git
```

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

### (TO CHECK IF IT IS NEEDED)
` tests/conftest.py`
```diff
 def pytest_addoption(parser: pytest.Parser) -> None:
     """Register custom pytest options."""
-    parser.addoption("--dburl", action="store", default="sqlite://")
+    #parser.addoption("--dburl", action="store", default="sqlite://")

```





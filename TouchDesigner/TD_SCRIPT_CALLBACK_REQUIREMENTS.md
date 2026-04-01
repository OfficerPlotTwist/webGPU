# TouchDesigner Callback Requirements

When writing or editing TouchDesigner callback scripts in this repo, preserve the built-in callback functions required by the operator type.

## Script TOP

Script TOP callback DATs must include the standard hooks TouchDesigner expects for stable cooking behavior.

Required pattern:

```python
def onGetCookLevel(scriptOp):
    return CookLevel.Automatic
```

And then the normal callbacks used by the Script TOP, for example:

```python
def onSetupParameters(scriptOp):
    ...

def onPulse(par):
    ...

def onCook(scriptOp):
    ...
```

## Practical Rule

- Do not replace TouchDesigner callback skeletons with plain utility modules.
- Keep the operator-specific callback signatures intact.
- If adding helper functions, add them below the required callback functions.
- For file-backed DAT workflows, treat the repo `.py` file as the source of truth and reload in TouchDesigner through the DAT file sync or refresh pulse.

## Recommendation For Future Work

If this continues to be easy to miss, add the same requirement to:

- editor `settings.md` guidance
- repo hooks or lint checks for `TouchDesigner/*.py`
- TouchDesigner workflow docs/templates used to scaffold callback DATs

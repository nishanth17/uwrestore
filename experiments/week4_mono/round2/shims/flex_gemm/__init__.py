"""Import-only stub for `flex_gemm`, used ONLY to satisfy the module-level import
in moge/model/v3.py:14 -> modules/sparse_unet.py:14 on a machine with no CUDA and
no Triton (Triton publishes no macOS wheel at all).

Nothing here is ever *executed* in a Round-2 run: MoGe-3 Step 0 is instantiated
with `model_kwargs={"refiner": None}` (an official from_pretrained override), so
`Sparse3DUNet` is never constructed, and `v3.py:168 if refine_steps > 0:` proves
the refiner is never called at refine_steps=0.  Every symbol below raises on use,
so any accidental execution fails loudly rather than silently approximating.
"""


class _Unavailable:
    def __init__(self, *a, **k):
        raise RuntimeError(
            "flex_gemm is a Round-2 import-only stub; the real Triton/CUDA "
            "implementation is unavailable on this machine. This symbol must "
            "never be constructed or called (MoGe-3 Step 3 is pending_cuda)."
        )


class config:
    AUTOTUNE_MODE = "never"

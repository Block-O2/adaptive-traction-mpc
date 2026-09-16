import sys

from setuptools import Extension, setup


if sys.platform == "win32":
    compile_args = ["/O2", "/fp:strict"]
    libraries: list[str] = []
else:
    compile_args = ["-O3", "-ffp-contract=off"]
    libraries = ["m"]


setup(
    ext_modules=[
        Extension(
            "traction_mpc_stage5._prefix_native",
            ["src/traction_mpc_stage5/_prefix_native.c"],
            extra_compile_args=compile_args,
            libraries=libraries,
        )
    ]
)

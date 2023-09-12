PYTHON?=python
PROJECT=acora
VERSION?=$(shell sed -ne 's|^__version__\s*=\s*"\([^"]*\)".*|\1|p' acora/__init__.py)
WITH_CYTHON=$(shell $(PYTHON) -c 'from Cython.Build import cythonize' && echo " --with-cython" || true)
PYTHON_WHEEL_BUILD_VERSION := "cp*"

MANYLINUX_IMAGES= \
    manylinux1_x86_64 \
    manylinux1_i686 \
    manylinux_2_24_x86_64 \
    manylinux_2_24_i686 \
    manylinux_2_24_aarch64 \
    manylinux_2_28_x86_64 \
    manylinux_2_28_aarch64 \
    musllinux_1_1_x86_64

all:    local

local:
	$(PYTHON) setup.py build_ext --inplace  $(WITH_CYTHON)

test:
	$(PYTHON) test.py -v

clean:
	${PYTHON} setup.py clean
	rm -f $(wildcard $(addprefix $(PROJECT)/*., so pyd pyc pyo))
	[ -z "$(WITH_CYTHON)" ] || rm -f $(PROJECT)/*.c

sdist: dist/$(PROJECT)-$(VERSION).tar.gz

dist/$(PROJECT)-$(VERSION).tar.gz:
	${PYTHON} setup.py sdist

qemu-user-static:
	docker run --rm --privileged hypriot/qemu-register

wheel:
	$(PYTHON) setup.py bdist_wheel

wheel_manylinux: sdist $(addprefix wheel_,$(MANYLINUX_IMAGES))
$(addprefix wheel_,$(filter-out %_x86_64, $(filter-out %_i686, $(MANYLINUX_IMAGES)))): qemu-user-static

wheel_%: dist/$(PROJECT)-$(VERSION).tar.gz
	@echo "Building wheels for $(PROJECT) $(VERSION)"
	time docker run --rm -t \
		-v $(shell pwd):/io \
		-e CFLAGS="-O3 -g0 -mtune=generic -pipe -fPIC" \
		-e LDFLAGS="$(LDFLAGS) -fPIC" \
		-e WHEELHOUSE=wheelhouse$(subst wheel_manylinux,,$@) \
		quay.io/pypa/$(subst wheel_,,$@) \
		bash -c 'for PYBIN in /opt/python/$(PYTHON_WHEEL_BUILD_VERSION)/bin; do \
		    $$PYBIN/python -V; \
		    { $$PYBIN/python -m pip wheel -w /io/$$WHEELHOUSE /io/$< & } ; \
		    done; wait; \
		    for whl in /io/$$WHEELHOUSE/$(PROJECT)-$(VERSION)-*-linux_*.whl; do auditwheel repair $$whl -w /io/$$WHEELHOUSE; done'

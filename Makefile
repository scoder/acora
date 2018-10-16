PYTHON?=python
PROJECT=acora
VERSION?=$(shell sed -ne 's|^version\s*=\s*"\([^"]*\)".*|\1|p' setup.py)
WITH_CYTHON=$(shell $(PYTHON) -c 'from Cython.Build import cythonize' && echo " --with-cython" || true)

MANYLINUX_IMAGE_X86_64=quay.io/pypa/manylinux1_x86_64
MANYLINUX_IMAGE_686=quay.io/pypa/manylinux1_i686

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

wheel_manylinux: wheel_manylinux64 wheel_manylinux32

wheel_manylinux32 wheel_manylinux64: dist/$(PROJECT)-$(VERSION).tar.gz
	@echo "Building wheels for $(PROJECT) $(VERSION)"
	mkdir -p wheelhouse_$(subst wheel_,,$@)
	time docker run --rm -t \
		-v $(shell pwd):/io \
		-e CFLAGS="-O3 -g0 -mtune=generic -pipe -fPIC" \
		-e LDFLAGS="$(LDFLAGS) -fPIC" \
		-e WHEELHOUSE=wheelhouse_$(subst wheel_,,$@) \
		$(if $(patsubst %32,,$@),$(MANYLINUX_IMAGE_X86_64),$(MANYLINUX_IMAGE_686)) \
		bash -c 'for PYBIN in /opt/python/*/bin; do \
		    $$PYBIN/python -V; \
		    { $$PYBIN/pip wheel -w /io/$$WHEELHOUSE /io/$< & } ; \
		    done; wait; \
		    for whl in /io/$$WHEELHOUSE/$(PROJECT)-$(VERSION)-*-linux_*.whl; do auditwheel repair $$whl -w /io/$$WHEELHOUSE; done'

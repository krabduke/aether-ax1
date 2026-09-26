BLENDER := /Applications/Blender.app/Contents/MacOS/Blender
BLEND   := build/aether.blend
SAMPLES ?= 64

.PHONY: all build verify audits render closeups export web stl manifest viewer cycle clean

all: build verify render web

cycle:                       ## print the thermodynamic design point
	python3 engine/cycle.py

build:                       ## generate geometry, assemble build/aether.blend
	$(BLENDER) --background --factory-startup --python engine/assemble.py
	python3 tools/make_manifest.py

verify:                      ## the definition of done
	python3 engine/verify.py
	python3 tools/audit_watertight.py
	python3 tools/audit_geometry.py
	python3 tools/audit_structure.py
	python3 tools/audit_intersect.py
	python3 tools/audit_support.py
	python3 tools/audit_ports.py
	python3 tools/audit_joints.py
	python3 tools/audit_rotor.py
	python3 tools/audit_manifest.py
	node tools/validate_viewer.mjs .

render:                      ## hero, front, cutaway, exploded, nozzle
	$(BLENDER) -b $(BLEND) -P engine/render.py -- all $(SAMPLES)

closeups:                    ## detail shots used to inspect the model
	$(BLENDER) -b $(BLEND) -P engine/render.py -- closeups $(SAMPLES)

export:
	$(BLENDER) -b $(BLEND) -P engine/export.py -- glb

web:                         ## decimated, Draco-compressed GLB for the viewer
	$(BLENDER) -b $(BLEND) -P engine/export.py -- web

stl:
	$(BLENDER) -b $(BLEND) -P engine/export.py -- stl

manifest:
	python3 tools/make_manifest.py

viewer:
	@echo "Serving http://localhost:8791/viewer/ -- Ctrl-C to stop"
	@python3 -m http.server 8791 --bind 127.0.0.1

clean:
	rm -rf build

bom:                         ## bill of materials: every part, its group, material, pieces, size
	python3 ../_shared/tools/make_bom.py . build/aether.blend bom.csv

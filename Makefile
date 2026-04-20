UDEV_RULE_FILE = 42-logitech-unify-permissions.rules
UDEV_RULES_SOURCE := rules.d/$(UDEV_RULE_FILE)
UDEV_RULES_SOURCE_UINPUT := rules.d-uinput/$(UDEV_RULE_FILE)
UDEV_RULES_DEST := /etc/udev/rules.d/

PIP_ARGS ?= .

.PHONY: install_ubuntu install_macos
.PHONY: install_apt install_brew install_pip
.PHONY: install_udev install_udev_uinput reload_udev uninstall_udev
.PHONY: format lint test

install_ubuntu: install_apt install_udev_uinput install_pip

install_macos: install_brew install_pip

install_apt:
	@echo "Installing Solaar dependencies via apt"
	sudo apt update
	sudo apt install libdbus-1-dev libglib2.0-dev libgtk-3-dev libgirepository1.0-dev

install_apt_python3.13:
	@echo "Installing Solaar dependencies via apt"
	sudo apt update
	sudo apt install libdbus-1-dev libglib2.0-dev libgtk-3-dev libgirepository-2.0-dev gobject-introspection

install_dnf:
	@echo "Installing Solaar dependencies via dnf"
	sudo dnf install gtk3 python3-devel python3-gobject python3-dbus python3-pyudev python3-psutil python3-xlib python3-yaml

install_bazzite:
	@echo "Layering GTK4/libadwaita + Python bindings via rpm-ostree."
	@echo "A reboot is required for rpm-ostree changes to take effect."
	sudo rpm-ostree install python3-gobject python3-pyudev python3-psutil \
		python3-xlib python3-yaml libadwaita gtk4 gobject-introspection hidapi
	@echo "Now reboot, then run: make run-dev"

run-dev:
	@test -f bin/solaar || (echo "ERROR: run from the Solaar repo root" && exit 1)
	@echo "Launching Solaar from source (gtk4-rewrite branch)."
	PYTHONPATH=lib python3 bin/solaar $(ARGS)

# --- User-level install for Bazzite (no sudo, no system package) ---
#
# Creates a venv at ~/.local/solaar that can see the rpm-ostree-layered
# python3-gobject, installs Solaar in editable mode, and wires up a systemd
# user service so Solaar starts at login.

SOLAAR_USER_VENV := $(HOME)/.local/solaar
SOLAAR_USER_BIN  := $(SOLAAR_USER_VENV)/bin/solaar
SOLAAR_SYSTEMD_DIR := $(HOME)/.config/systemd/user

install-user:
	@test -f bin/solaar || (echo "ERROR: run from the Solaar repo root" && exit 1)
	@echo "Creating venv at $(SOLAAR_USER_VENV) with system-site-packages."
	python3 -m venv --system-site-packages $(SOLAAR_USER_VENV)
	$(SOLAAR_USER_VENV)/bin/pip install --upgrade pip
	$(SOLAAR_USER_VENV)/bin/pip install -e .
	@echo ""
	@echo "Installed. Manual launch: $(SOLAAR_USER_BIN)"
	@echo "Autostart: make enable-autostart"

enable-autostart:
	@test -x $(SOLAAR_USER_BIN) || (echo "ERROR: run 'make install-user' first" && exit 1)
	mkdir -p $(SOLAAR_SYSTEMD_DIR)
	cp systemd/solaar.service $(SOLAAR_SYSTEMD_DIR)/solaar.service
	systemctl --user daemon-reload
	systemctl --user enable --now solaar.service
	@echo ""
	@echo "Solaar is running. Check status:  systemctl --user status solaar"
	@echo "View logs:                        journalctl --user -u solaar -f"
	@echo "Disable autostart:                make disable-autostart"

disable-autostart:
	-systemctl --user disable --now solaar.service
	rm -f $(SOLAAR_SYSTEMD_DIR)/solaar.service
	systemctl --user daemon-reload

uninstall-user: disable-autostart
	rm -rf $(SOLAAR_USER_VENV)
	@echo "Removed $(SOLAAR_USER_VENV)"

install_brew:
	@echo "Installing Solaar dependencies via brew"
	brew update
	brew install hidapi gtk+3 pygobject3 gobject-introspection

install_pip:
	@echo "Installing Solaar via pip"
	python -m pip install --upgrade pip
	pip install $(PIP_ARGS)

install_pipx:
	@echo "Installing Solaar via pipx"
	pipx install --system-site-packages $(PIP_ARGS)

install_udev:
	@echo "Copying Solaar udev rule to $(UDEV_RULES_DEST)"
	sudo cp $(UDEV_RULES_SOURCE) $(UDEV_RULES_DEST)
	make reload_udev

install_udev_uinput:
	@echo "Copying Solaar udev rule (uinput) to $(UDEV_RULES_DEST)"
	sudo cp $(UDEV_RULES_SOURCE_UINPUT) $(UDEV_RULES_DEST)
	make reload_udev

reload_udev:
	@echo "Reloading udev rules"
	sudo udevadm control --reload-rules

uninstall_udev:
	@echo "Removing Solaar udev rules from $(UDEV_RULES_DEST)"
	sudo rm -f $(UDEV_RULES_DEST)/$(UDEV_RULE_FILE)
	make reload_udev

format:
	@echo "Formatting Solaar code"
	ruff format .

lint:
	@echo "Linting Solaar code"
	ruff check . --fix

test:
	@echo "Running Solaar tests"
	pytest --cov --cov-report=xml

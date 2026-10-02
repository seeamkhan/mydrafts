#!/usr/bin/env bash
# Remove everything install.sh added and restore the old setxkbmap Cmd/Ctrl swap.
# Usage: sudo ./uninstall.sh
set -uo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo: sudo $0" >&2; exit 1; }
U=${SUDO_USER:?Run this with sudo from your normal user account}
H=$(getent passwd "$U" | cut -d: -f6)
KEYD_SRC=$H/.local/src/keyd
QUIRKS=/etc/libinput/local-overrides.quirks
A=$H/.config/autostart

sudo -u "$U" pkill -f keyd-application-mapper
for p in $(pgrep -f '^/usr/local/bin/libinput-three-finger-drag'); do pkill -P "$p"; kill "$p"; done

systemctl disable --now keyd
[ -d "$KEYD_SRC" ] && make -C "$KEYD_SRC" uninstall          # also removes the keyd group
rm -f /etc/keyd/default.conf /usr/local/bin/libinput-three-finger-drag \
      /etc/polkit-1/rules.d/50-macmode-keyd.rules
rm -rf /etc/systemd/system/keyd.service.d /var/lib/macmode
systemctl daemon-reload

# Drop the keyd block from the libinput quirks file (remove the file if nothing else is left).
if [ -f "$QUIRKS" ]; then
    sed -i '/^# Installed to \/etc\/libinput/,/^AttrKeyboardIntegration=internal$/d; /^\[keyd virtual keyboard\]$/,/^AttrKeyboardIntegration=internal$/d' "$QUIRKS"
    grep -q '[^[:space:]]' "$QUIRKS" || rm -f "$QUIRKS"
fi

gpasswd -d "$U" input >/dev/null 2>&1

rm -f "$A/macmode.desktop" "$A/touchegg.desktop" "$H/.local/bin/macmode" \
      "$H/.local/share/applications/macmode.desktop" "$H/.config/keyd/app.conf"
rm -rf "$H/.config/macmode"

# Restore the old swap autostart (from the newest backup, else recreate it).
src=$(ls -d "$H"/mint-macbook-backup-*/autostart/"Swap Cmd and Ctrl.desktop" 2>/dev/null | tail -1)
if [ -n "$src" ]; then
    sudo -u "$U" cp "$src" "$A/"
else
    sudo -u "$U" tee "$A/Swap Cmd and Ctrl.desktop" >/dev/null <<'EOF'
[Desktop Entry]
Type=Application
Name=Swap Cmd and Ctrl
Exec=setxkbmap -option ctrl:swap_lwin_lctl -option ctrl:swap_rwin_rctl
OnlyShowIn=XFCE;
Terminal=false
Hidden=false
EOF
fi

echo "Uninstalled. Log out and back in to finish."

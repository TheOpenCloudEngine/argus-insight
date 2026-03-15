%define _bindir /usr/local/bin
%define _unitdir /usr/lib/systemd/system
%define _build_id_links none

Name:           zot
Version:        %{zot_version}
Release:        1%{?dist}
Summary:        OCI Distribution Specification compliant container image registry
License:        Apache-2.0
URL:            https://github.com/TheOpenCloudEngine/zot-registry-service
Packager:       Open Cloud Engine Community

Source0:        zot
Source1:        zot.service
Source2:        config.json
Source3:        credentials.json
Source4:        generate_certs.sh
Source5:        hosts.txt
Source6:        htpasswd

BuildArch:      x86_64

Requires:       jq

%description
Zot is a production-ready, open-source, vendor-neutral OCI-native container
image registry that is compliant with the OCI Distribution Specification.
It supports OCI image and artifact types including container images, Helm charts,
OPA bundles, and Singularity.

%install
install -d -m 0755 %{buildroot}%{_bindir}
install -m 0755 %{SOURCE0} %{buildroot}%{_bindir}/zot

install -d -m 0755 %{buildroot}%{_unitdir}
install -m 0644 %{SOURCE1} %{buildroot}%{_unitdir}/zot.service

install -d -m 0755 %{buildroot}/etc/zot
install -m 0644 %{SOURCE2} %{buildroot}/etc/zot/config.json
install -m 0600 %{SOURCE3} %{buildroot}/etc/zot/credentials.json
install -m 0600 %{SOURCE6} %{buildroot}/etc/zot/htpasswd

install -d -m 0755 %{buildroot}/etc/zot/certs
install -m 0755 %{SOURCE4} %{buildroot}/etc/zot/certs/generate_certs.sh
install -m 0644 %{SOURCE5} %{buildroot}/etc/zot/certs/hosts.txt

install -d -m 0755 %{buildroot}/var/lib/zot

%files
%{_bindir}/zot
%{_unitdir}/zot.service
%dir /etc/zot
%config(noreplace) /etc/zot/config.json
%config(noreplace) /etc/zot/credentials.json
%config(noreplace) /etc/zot/htpasswd
%dir /etc/zot/certs
/etc/zot/certs/generate_certs.sh
%config(noreplace) /etc/zot/certs/hosts.txt
%dir /var/lib/zot

%pre
getent group zot >/dev/null || groupadd -r zot
getent passwd zot >/dev/null || useradd -r -g zot -d /var/lib/zot -s /sbin/nologin -c "Zot Registry" zot
exit 0

%post
if [ $1 -eq 1 ] && command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload >/dev/null 2>&1 || :
    systemctl enable zot.service >/dev/null 2>&1 || :
fi
echo ""
echo "================================================================="
echo " Zot Registry 설치가 완료되었습니다."
echo "================================================================="
echo ""
echo " 1. Zot을 실행할 서버의 호스트명을 /etc/zot/certs/hosts.txt 파일에 추가하십시오."
echo ""
echo " 2. /etc/zot/certs/generate_certs.sh 스크립트를 실행하여 인증서를 생성하십시오."
echo ""
echo " 3. /etc/zot/config.json 파일에 인증서의 경로를 변경하십시오."
echo ""
echo " 4. /etc/zot/credentials.json 파일에 Zot에 push를 위한 username, password를 지정하십시오."
echo ""
echo " 설정 완료 후: systemctl start zot"
echo "================================================================="

%preun
if [ $1 -eq 0 ] && command -v systemctl >/dev/null 2>&1; then
    systemctl stop zot.service >/dev/null 2>&1 || :
    systemctl disable zot.service >/dev/null 2>&1 || :
fi

%postun
if [ $1 -ge 1 ] && command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload >/dev/null 2>&1 || :
fi

%changelog

%define name synapse-agent
%define version 3.1.0
%define release 1
%define protocol_version 1.0

Name: %{name}
Version: %{version}
Release: %{release}
Summary: Universal Autonomous Agent Platform

License: MIT
URL: https://github.com/synapse/synapse
Source0: %{name}-%{version}.tar.gz

BuildRequires: python3 >= 3.11
BuildRequires: python3-pip
Requires: python3 >= 3.11
Requires: python3-pip

%description
Synapse is a distributed cognitive platform for autonomous agents.

Features:
- Cross-platform support (Windows, macOS, Linux)
- Capability-based security model
- Self-evolution capabilities
- Protocol version %{protocol_version} compliant

%prep
%setup -q

%build
# No build step required

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/usr/lib/synapse
mkdir -p $RPM_BUILD_ROOT/usr/bin
cp -r synapse $RPM_BUILD_ROOT/usr/lib/synapse/
cp -r config $RPM_BUILD_ROOT/usr/lib/synapse/
cp -r skills $RPM_BUILD_ROOT/usr/lib/synapse/
cp requirements.txt $RPM_BUILD_ROOT/usr/lib/synapse/
ln -s /usr/lib/synapse/synapse/main.py $RPM_BUILD_ROOT/usr/bin/synapse

%post
pip3 install -r /usr/lib/synapse/requirements.txt

%preun
# Cleanup

%files
%defattr(-,root,root)
/usr/lib/synapse
/usr/bin/synapse

%changelog
* Thu Feb 20 2026 Synapse Contributors <support@synapse.org> - 3.1.0-1
- Initial RPM package
- Protocol version 1.0

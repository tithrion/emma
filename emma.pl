#!/usr/bin/perl -w

######################################################
######################################################
## emma.pl - configure emagic MIDI interfaces       ##
## Author:  Steffen Klein, steffen@klein-network.de ##
## Version: 1.0     2012-01-10                      ##
## License: GPLv2                                   ##
######################################################
######################################################

=pod

=head1 NAME

emma.pl

=head1 DESCRIPTION                                                                                                                  $
                                                                                                                                    $
This program configures the operating mode of emagic MIDI devices (UNITOR8,AMT8,MT4)

=head1 SYNOPSIS

emma.pl [options]

=head1 OPTIONS

emma.pl <MODE> <PORT>

=over

=item   B<-m/--mode=MODE>

Operating Mode (patch/usb) to set

=item   B<-p/--port=PORT>                                                                                                           $

Target MIDI port (UNITOR8,AMT8,MT4)

=item   B<-h/--help>                                                                                                                $
                                                                                                                                    $
Help

=item   B<-v/--version>

version information

=back

=cut

use strict;
use Getopt::Long;
use Pod::Usage;
use MIDI::ALSA;
use String::HexConvert ':all';

# version string
my $version = '1.0';

# get command-line parameters
my ($mode, $port, $help, $showVersion);
GetOptions(
        "m|mode=s"      => \$mode,
        "p|port=s"      => \$port,
        "h|help"        => \$help,
        "v|version"     => \$showVersion
);

# should print version?
if ($showVersion) { print "$version\n"; exit 0; }

# should print help?
if ($help) { pod2usage(-verbose  => 2); }

# got all needed options?
if (!$mode || !$port) { pod2usage(1); }

# sysex-commands
my $patchmode = hex_to_ascii("0020316410007F00");
my $usbmode = hex_to_ascii("002031640F007F");

my $string;
if ($mode eq 'usb'){
        $string = $usbmode;
} elsif ($mode eq 'patch'){
        $string = $patchmode;
}

my $client_name = 'emma' ;

# define client                                                                                                                     $
MIDI::ALSA::client( $client_name, 0, 1, 0 );

# connect client to interface
MIDI::ALSA::connectto( 1, $port, 'Broadcast' );

my @alsaevent = MIDI::ALSA::sysex( 1, $string );

#if ($alsaevent[0] == SND_SEQ_EVENT_PORT_UNSUBSCRIBED()) { last; }
MIDI::ALSA::output( @alsaevent );

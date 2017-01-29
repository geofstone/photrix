from math import pi
from datetime import datetime, timedelta, timezone
import os
import json
import ephem
from copy import copy
from photrix.util import Timespan, RaDec, hex_degrees_as_degrees

__author__ = "Eric Dose :: Bois d'Arc Observatory, Kansas"

PHOTRIX_ROOT_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DIRECTORY = os.path.join(PHOTRIX_ROOT_DIRECTORY, "site")
MOON_PHASE_NO_FACTOR = 0.05
MIN_MOON_DIST = 45  # in degrees


class Site:
    """
    Object: holds site info (no instrument or AN info), read from a json site file.
    Usage: site = Site("BDO_Kansas")
    Attributes (string unless otherwise noted):
        .name : site's name
        .filename : json file name
        .description : site description
        .longitude, .latitude : of site, in degrees (float)
        .elevation : of site, in meters (float)
        .min_altitude : in degrees (float)
        .twilight_sun_alt : in degrees (float)
        .is_valid : True if attribute values appear valid (boolean)
    """
    def __init__(self, site_name, site_directory=SITE_DIRECTORY):
        site_fullpath = os.path.join(site_directory, site_name + ".json")
        with open(site_fullpath) as data_file:
            data = json.load(data_file)
        self.name = data.get("name", site_name)
        self.filename = site_name + ".json"
        self.description = data.get("description", "")
        self.longitude = data.get("longitude", None)  # West longitude is negative.
        if self.longitude is not None:
            self.longitude = hex_degrees_as_degrees(str(self.longitude))
        self.latitude = data.get("latitude", None)  # South latitude is negative.
        if self.latitude is not None:
            self.latitude = hex_degrees_as_degrees(str(self.latitude))
        self.elevation = data.get("elevation", 500)  # in meters
        self.min_altitude = data.get("min_altitude", 0)
        self.twilight_sun_alt = data.get("twilight_sun_alt", -10)

        is_valid = (self.longitude is not None) and (self.latitude is not None)  # default
        if is_valid:
            if not ((self.longitude >= -180) and (self.longitude <= +180)):
                is_valid = False
            if not ((self.latitude >= -90) and (self.longitude <= +90)):
                is_valid = False
        self.is_valid = is_valid

    def __repr__(self):
        return "site('" + self.filename + "')"

    def __str__(self):
        return self.__repr__() + " valid=" + str(self.is_valid)


class Instrument:
    """
    Object: holds instrument info (no site or AN info).
    Usage: inst = Instrument("Borea")
    Attributes (string unless otherwise noted):
        .name :
        .filename :
        .description :
        .min_distance_full_moon : in degrees (float)
        .mount["model"] :
        .mount["slew_rate_ra"] : in deg/sec (float)
        .mount["slew_rate_dec"] : in degrees (float)
        .mount["sec_to_speed_ra"] : in seconds (float)
        .mount["sec_to_speed_dec"] : in seconds (float)
        .ota["model"] :
        .ota["focal_length_mm"] : in millimeters (float)
        .camera["model"] :
        .camera["pixels_x"] : (int)
        .camera["pixels_y"] : (int)
        .camera["microns_per_pixel"] : (float)
        .camera["shortest_exposure"] : in seconds (float)
        .camera["saturation_adu"] : maximum ADUs while linear (float)
        .filters[filter(string)]["reference_exposure_mag10"] : possibly several (float)
        .filters[filter(string)]["transform"][color(string)] : possibly several (float)
        .is_valid : True if attribute values appear valid (boolean)
    """
    def __init__(self, instrument_name):
        photrix_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        instrument_fullpath = os.path.join(photrix_root_dir, "instrument",
                                           (instrument_name + ".json"))
        with open(instrument_fullpath) as data_file:
            data = json.load(data_file)

        self.name = data.get("name", instrument_name)
        self.filename = instrument_name + ".json"
        self.description = data.get("description", "")
        self.min_distance_full_moon = data.get("min_distance_full_moon", 60)  # degrees
        mount = data.get("mount")
        mount["model"] = mount.get("model", "")
        mount["slew_rate_ra"] = mount.get("slew_rate_ra", 4)
        mount["slew_rate_dec"] = mount.get("slew_rate_dec", 4)
        mount["sec_to_speed_ra"] = mount.get("sec_to_speed_ra", 1)
        mount["sec_to_speed_dec"] = mount.get("secto_speed_dec", 1)
        self.mount = mount

        ota = data.get("ota")
        ota["model"] = ota.get("model", "")
        ota["focal_length_mm"] = ota.get("focal_length_mm", 0)
        self.ota = ota

        camera = data.get("camera")
        camera["model"] = camera.get("model", "")
        camera["pixels_x"] = camera.get("pixels_x", 0)
        camera["pixels_y"] = camera.get("pixels_y", 0)
        camera["microns_per_pixel"] = camera.get("microns_per_pixel", 0)
        camera["shortest_exposure"] = camera.get("shortest_exposure", 0)
        camera["saturation_adu"] = camera.get("saturation_adu", 64000)
        self.camera = camera

        self.filters = data.get("filters")

        is_valid = True  # default to be falsified if any error.

        self.is_valid = is_valid

    def filter_list(self):
        return list(self.filters.keys())

    def __repr__(self):
        return "Instrument('" + self.filename + "')"

    def __str__(self):
        return self.__repr__() + " valid=" + str(self.is_valid)


class Astronight:
    def __init__(self, an_date_string, site_name):
        """
        Object: relevant info specific to one observing night at one site.
        Usage: an = Astronight("20160102", "BDO_Kansas")
        Attributes (string unless otherwise noted):
            .an_date_string : as "20161011"
            .site_name : as "BDO_Kansas"
            .site : this site (Site object)
            ._observer : this site and this astronight (ephem.Observer object)
            .ts_dark : Timespan(twilight_dusk, twilight_dawn) for this astronight.
            .local_middark_ut : local mid-dark time, this astronight, in UTC time (datetime object)
            .local_middark_jd : local mid-dark time, this astronight, in Julian date (float)
            .local_middark_lst : local mid-dark time, this astronight, LST in degrees (float)
            .moon_radec : moon location at middark (RaDec object)
            .moon_phase : moon phase at middark (float, range 0-1)
            .ts_dark_no_moon : Timespan both dark and moonless (or just dark if moon phase < MIN)

       """
        self.an_date_string = an_date_string
        self.site_name = site_name
        self.site = Site(site_name)

        site_obs = ephem.Observer()  # for local use (within __init__()).
        site_obs.lat, site_obs.lon = str(self.site.latitude), str(self.site.longitude)
        site_obs.elevation = self.site.elevation

        # get local middark times for requested Astronight.
        an_year = int(an_date_string[0:4])
        an_month = int(an_date_string[4:6])
        an_day = int(an_date_string[6:8])
        approx_midnight_utc = \
            datetime(an_year, an_month, an_day, 0, 0, 0).replace(tzinfo=timezone.utc) + \
            timedelta(hours=-self.site.longitude / 15.0) + \
            timedelta(hours=+24)

        sun = ephem.Sun()
        site_obs.horizon = str(self.site.twilight_sun_alt)
        sun.compute(site_obs)
        twilight_dusk = site_obs.previous_setting(sun,
            start=approx_midnight_utc).datetime().replace(tzinfo=timezone.utc)
        twilight_dawn = site_obs.next_rising(sun,
            start=approx_midnight_utc).datetime().replace(tzinfo=timezone.utc)
        self.ts_dark = Timespan(twilight_dusk, twilight_dawn)
        self.local_middark_utc = self.ts_dark.midpoint
        self.local_middark_jd = ephem.julian_date(self.local_middark_utc)
        site_obs.date = self.local_middark_utc
        self.local_middark_lst = site_obs.sidereal_time() * 180. / pi  # in degrees

        # Prep moon, using RaDec at local mid-dark.
        moon = ephem.Moon()
        site_obs.date = self.local_middark_utc
        site_obs.horizon = "0"  # when moon is at all visible
        site_obs.epoch = '2000'
        moon.compute(site_obs)
        self.moon_radec = RaDec(str(moon.ra), str(moon.dec))
        self.moon_phase = moon.moon_phase
        # get .ts_dark_no_moon (Timespan object) for this Astronight.
        if self.moon_phase <= MOON_PHASE_NO_FACTOR:
            self.ts_dark_no_moon = self.ts_dark
        else:
            moonrise_1 = site_obs.previous_rising(moon,
                start=approx_midnight_utc).datetime().replace(tzinfo=timezone.utc)
            moonset_1 = site_obs.next_setting(moon,
                start=moonrise_1).datetime().replace(tzinfo=timezone.utc)
            ts_moon_up_1 = Timespan(moonrise_1, moonset_1)
            moonset_2 = site_obs.next_setting(moon,
                start=approx_midnight_utc).datetime().replace(tzinfo=timezone.utc)
            moonrise_2 = site_obs.previous_rising(moon,
                start=moonset_2).datetime().replace(tzinfo=timezone.utc)
            ts_moon_up_2 = Timespan(moonrise_2, moonset_2)
            self.ts_dark_no_moon = self.ts_dark.subtract(ts_moon_up_1).subtract(ts_moon_up_2)
    # TODO: Prep all other solar-system bodies, using their RaDecs at local mid-dark.
    # jupiter = ephem.Jupiter(obs)
    # self.jupiter_radec = RaDec(str(jupiter.ra), str(jupiter.dec))
    # saturn = ephem.Saturn(obs)
    # self.saturn_radec = RaDec(str(saturn.ra), str(saturn.dec))
    # venus = ephem.Venus(obs)
    # self.venus_radec = RaDec(str(venus.ra), str(venus.dec))

    def ts_observable(self, target_radec=RaDec('0', '+0'), min_alt=None, min_moon_dist=None):
        """
        Returns Timespan object defining when this RA,Dec may be observed during this astronight.
        Site data are taken from ephem Observer object self._observer stored in this object.
        Usage: ts = an.observable(util.RaDec(fov.ra, fov.dec), +28, 45)
        :param target_radec: required, a RaDec position for the object to be observed.
        :param min_alt: min object altitude to observe, in degrees; default->use Site min alt.
        :param min_moon_dist: min distance from moon to observe, enforced only when moon is up,
           in degrees; default->use Site min moon distance.
           Set to 0 to ignore moon (i.e., moon makes no difference to observable times).
           Set to >=180 to ignore moon phase (i.e., moon must be down to observe at all).
           [User may want to set this value by using a Lorentzian fn, as RTML does,
              using (possibly auto-computed) distance and days-from-full-moon values.]
        :return: Timespan object of start and end times (UT) that observing is allowed.
        """
        if min_alt is None:
            min_alt = self.site.min_altitude
        if min_moon_dist is None:
            min_moon_dist = MIN_MOON_DIST

        obs = ephem.Observer()  # for local use.
        obs.lat, obs.lon = str(self.site.latitude), str(self.site.longitude)
        obs.elevation = self.site.elevation
        obs.horizon = str(min_alt)
        obs.date = self.local_middark_utc
        target_ephem = ephem.FixedBody()  # so named to suggest restricting its use to ephem.
        target_ephem._epoch = '2000'
        target_ephem._ra, target_ephem._dec = target_radec.as_hex  # text: RA in hours, Dec in deg
        target_ephem.compute(obs)

        # Compute object-up Timespan, watching for exceptions (i.e., obj Never up or Always up).
        try:
            obj_rise_1 = obs.previous_rising(target_ephem,
                start=self.local_middark_utc).datetime().replace(tzinfo=timezone.utc)
        except ephem.NeverUpError:
            # return zero-duration Timespans.
            obj_ts_1 = Timespan(self.local_middark_utc, self.local_middark_utc)
            obj_ts_2 = obj_ts_1
        except ephem.AlwaysUpError:
            # return Timespans of astronight's entire dark period.
            obj_ts_1 = self.ts_dark
            obj_ts_2 = obj_ts_1
        else:
            # get remaining rise and set times, return the 2 candidate Timespans.
            obj_set_1 = obs.next_setting(target_ephem,
                start=obj_rise_1).datetime().replace(tzinfo=timezone.utc)
            obj_set_2 = obs.next_setting(target_ephem,
                start=self.local_middark_utc).datetime().replace(tzinfo=timezone.utc)
            obj_rise_2 = obs.previous_rising(target_ephem,
                start=obj_set_2).datetime().replace(tzinfo=timezone.utc)
            obj_ts_1 = Timespan(obj_rise_1, obj_set_1)
            obj_ts_2 = Timespan(obj_rise_2, obj_set_2)
        moon_dist_deg = RaDec(self.moon_radec.ra, self.moon_radec.dec).degrees_from(target_radec)
        # print("moon: ", RaDec(self.moon_radec.ra, self.moon_radec.dec))
        # print("target: ", RaDec(target_ephem.ra, target_ephem.dec))
        # print("moon dist deg:", moon_dist_deg, "min_moon_dist:", min_moon_dist)
        if moon_dist_deg > min_moon_dist:
            obj_avail_1 = obj_ts_1.intersect(self.ts_dark)
            obj_avail_2 = obj_ts_2.intersect(self.ts_dark)
        else:
            obj_avail_1 = obj_ts_1.intersect(self.ts_dark_no_moon)
            obj_avail_2 = obj_ts_2.intersect(self.ts_dark_no_moon)
        # print("obj_avail_1", obj_avail_1)
        # print("obj_avail_2", obj_avail_2)
        ts_obj_avail = Timespan.longer(obj_avail_1, obj_avail_2, on_tie="earlier")
        return ts_obj_avail

    def ts_fov_observable(self, fov, min_alt=None, min_moon_dist=None):
        """ Convenience function.
        Returns Timespan object containing when FOV (or rather, its center RaDec is observable
        during this Astronight.
        Usage: ts = an.when_FOV_observable(FOV, min_alt, min_moon_dist)
        """
        return self.ts_observable(RaDec(fov.ra, fov.dec), min_alt, min_moon_dist)

    def datetime_utc_from_hhmm(self, hhmm_string):
        mid_dark = self.local_middark_utc
        hour_hhmm = int(hhmm_string[0:2])
        minute_hhmm = int(hhmm_string[2:4])
        test_dt = mid_dark.replace(hour=hour_hhmm, minute=minute_hhmm)
        delta_days = round((test_dt - mid_dark).total_seconds() / (24 * 3600))  # adjust if needed.
        best_dt = test_dt - timedelta(days=delta_days)
        return best_dt

    def __repr__(self):
        return "Astronight '" + self.an_date_string + "' at site '" + self.site_name + "'."

    def acp_header_string(self):
        """ Returns an info string to include atop an ACP plan file, as:
            ; sunset-rise 0033-1145 UT , -11 deg alt @ 0119-1055 UT  //  LST = cdt + 1128.
            ; moon 15% @ (~22h04,-10) rise 0936 UT
        Usage: s = an.acp_header_string()
        """
        # TODO: redo this method with: (1) template from more recent ACP plans, and
        #                              (2) the better facilities in current Astronight class.

        site_obs = ephem.Observer()
        site_obs.lat, site_obs.lon = str(self.site.latitude), str(self.site.longitude)
        site_obs.elevation = self.site.elevation
        sun = ephem.Sun(site_obs)
        # moon = ephem.Moon(site_obs)

        # Handle sun data:
        site_obs.horizon = '0'
        sunset_utc = site_obs.previous_setting(sun, self.local_middark_utc)\
            .datetime().replace(tzinfo=timezone.utc)
        sunset_utc_string = sunset_utc.strftime('%H%M')
        dark_start_utc_string = self.ts_dark.start.strftime('%H%M')
        site_obs.date = self.ts_dark.start
        dark_start_lst = site_obs.sidereal_time()
        dark_start_lst_minutes = round(60.0 * ((dark_start_lst * 180.0 / pi) / 15.0))
        dark_start_lst_string = '{0:02d}'.format(int(dark_start_lst_minutes / 60)) + \
                       '{0:02d}'.format(dark_start_lst_minutes % 60)

        sunrise_utc = site_obs.next_rising(sun, self.local_middark_utc)\
            .datetime().replace(tzinfo=timezone.utc)
        sunrise_utc_string = sunrise_utc.strftime('%H%M')
        dark_end_utc_string = self.ts_dark.end.strftime('%H%M')
        site_obs.date = self.ts_dark.end
        dark_end_lst = site_obs.sidereal_time()
        dark_end_lst_minutes = round(60.0 * ((dark_end_lst * 180.0 / pi) / 15.0))
        dark_end_lst_string = '{0:02d}'.format(int(dark_end_lst_minutes / 60)) + \
                       '{0:02d}'.format(dark_end_lst_minutes % 60)
        # site_obs.date = sunrise_utc
        # sunrise_lst = site_obs.sidereal_time()
        #
        # sunrise_lst_minutes = round(60.0 * ((sunrise_lst * 180.0 / pi) / 15.0))
        # sunrise_lst_string = '{0:02d}'.format(int(sunrise_lst_minutes / 60)) + \
        #                '{0:02d}'.format(sunrise_lst_minutes % 60)

        # Handle moon data:
        moon_phase_string = '{0:d}%'.format(round(100 * self.moon_phase))
        moon_ra = round(self.moon_radec.ra / 15, 1)
        moon_dec = round(self.moon_radec.dec)
        moon_radec_string = ('({0:.1f}h,{1:+d}' + u'\N{DEGREE SIGN}' + ')').\
            format(moon_ra, moon_dec)
        # need moon logic here  [ rise vs set; also add "no factor" if phase < threshold ]
        if self.ts_dark_no_moon.seconds <= 0:
            dark_no_moon_string = 'MOON UP all night.'
        elif self.ts_dark_no_moon == self.ts_dark:
            dark_no_moon_string = 'MOON DOWN all night.'
        else:
            dark_no_moon_string = 'no moon: ' + \
                                  self.ts_dark_no_moon.start.strftime('%H%M') + '-' + \
                                  self.ts_dark_no_moon.end.strftime('%H%M') + ' UT'

        # Handle LST vs UT:
        lst_middark_seconds = self.local_middark_lst / 15 * 3600
        utc_middark_seconds = self.local_middark_utc.hour * 3600 + \
                              self.local_middark_utc.minute * 60 + \
                              self.local_middark_utc.second + \
                              self.local_middark_utc.microsecond/1000000.0
        diff_seconds = (lst_middark_seconds - utc_middark_seconds) % (24 * 3600)  # to make > 0.
        diff_hour = int(diff_seconds/3600)
        diff_minute = round((diff_seconds - (diff_hour*3600)) / 60)
        lst_vs_utc_string = '{0:02d}'.format(diff_hour) + '{0:02d}'.format(diff_minute)

        # Construct ACP header string:
        header_string = '; sun --- down: ' + \
                        sunset_utc_string + '-' + sunrise_utc_string + ' UT,   ' + \
                        'dark(' + '{0:+2d}'.format(round(self.site.twilight_sun_alt)) + \
                        u'\N{DEGREE SIGN}' + '): ' + \
                        dark_start_utc_string + '-' + dark_end_utc_string + ' UT  = ' + \
                        dark_start_lst_string + '-' + dark_end_lst_string + ' LST\n'
        header_string += '; moon -- ' + moon_phase_string + ' ' + moon_radec_string + \
                         '   ' + dark_no_moon_string + '\n'
        header_string += '; LST = UT + ' + lst_vs_utc_string + ' (middark)\n'
        return header_string




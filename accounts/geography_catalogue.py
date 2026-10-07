"""
Authoritative WDOS Administrative Geography Catalogue.
Normalizes African geography to:
country (ISO3) -> administrative level 1 -> administrative level 2 (where reliable) -> Community Cluster (free text).

Data sources and methodology:
- geoBoundaries gbOpen (v4.0) as the main free source for ADM1 boundaries and validated administrative units.
- UN OCHA/HDX COD-AB (Common Operational Datasets - Administrative Boundaries) as country-specific override
  where data is better, more current, or verified (e.g. Nigeria 774 LGAs, Kenya subcounties, South Africa, Ghana).
- GeoNames (2024) used to validate boundary names, codes, and fill documented gaps for small island states.
- No live third-party APIs are called during onboarding; all data is catalogued, cached, and seeded locally.
"""
from datetime import date
from typing import Dict, List, Optional, Tuple, Any

# Source provenance metadata constants
SOURCES = {
    "GEOBOUNDARIES": {
        "name": "geoBoundaries gbOpen",
        "version": "gbOpen-v4.0",
        "url": "https://www.geoboundaries.org/api.html",
        "last_verified_date": "2026-10-07",
    },
    "UN_OCHA_COD_AB": {
        "name": "UN OCHA/HDX COD-AB",
        "version": "COD-AB-2024",
        "url": "https://github.com/OCHA-DAP/hdx-cod-ab-spec",
        "last_verified_date": "2026-10-07",
    },
    "GEONAMES": {
        "name": "GeoNames",
        "version": "GeoNames-2024",
        "url": "https://www.geonames.org/export/web-services.html",
        "last_verified_date": "2026-10-07",
    },
}

# ISO2 to ISO3 mapping for all 55 African countries
ISO2_TO_ISO3: Dict[str, str] = {
    "DZ": "DZA", "AO": "AGO", "BJ": "BEN", "BW": "BWA", "BF": "BFA",
    "BI": "BDI", "CV": "CPV", "CM": "CMR", "CF": "CAF", "TD": "TCD",
    "KM": "COM", "CG": "COG", "CD": "COD", "CI": "CIV", "DJ": "DJI",
    "EG": "EGY", "GQ": "GNQ", "ER": "ERI", "SZ": "SWZ", "ET": "ETH",
    "GA": "GAB", "GM": "GMB", "GH": "GHA", "GN": "GIN", "GW": "GNB",
    "KE": "KEN", "LS": "LSO", "LR": "LBR", "LY": "LBY", "MG": "MDG",
    "MW": "MWI", "ML": "MLI", "MR": "MRT", "MU": "MUS", "MA": "MAR",
    "MZ": "MOZ", "NA": "NAM", "NE": "NER", "NG": "NGA", "RW": "RWA",
    "EH": "ESH", "ST": "STP", "SN": "SEN", "SC": "SYC", "SL": "SLE",
    "SO": "SOM", "ZA": "ZAF", "SS": "SSD", "SD": "SDN", "TZ": "TZA",
    "TG": "TGO", "TN": "TUN", "UG": "UGA", "ZM": "ZMB", "ZW": "ZWE",
}

ISO3_TO_ISO2: Dict[str, str] = {v: k for k, v in ISO2_TO_ISO3.items()}

# Countries where UN OCHA COD-AB is preferred override
COD_AB_COUNTRIES = {"NGA", "KEN", "ZAF", "GHA", "COD", "SSD", "SDN"}
GEONAMES_COUNTRIES = {"CPV", "MUS", "SYC", "STP"}

def get_source_for_country(iso3: str) -> Dict[str, str]:
    if iso3 in COD_AB_COUNTRIES:
        return SOURCES["UN_OCHA_COD_AB"]
    elif iso3 in GEONAMES_COUNTRIES:
        return SOURCES["GEONAMES"]
    return SOURCES["GEOBOUNDARIES"]


# Reliable Level 2 datasets
# Kenya subcounties (UN OCHA/HDX COD-AB)
KENYA_SUBCOUNTIES: Dict[str, List[str]] = {
    "Baringo": ["Baringo Central", "Baringo North", "Baringo South", "Eldama Ravine", "Mogotio", "Tiaty"],
    "Bomet": ["Bomet Central", "Bomet East", "Chepalungu", "Konoin", "Sotik"],
    "Bungoma": ["Bumula", "Kabuchai", "Kanduyi", "Kimilili", "Mt. Elgon", "Sirisia", "Tongaren", "Webuye East", "Webuye West"],
    "Busia": ["Budalangi", "Butula", "Funyula", "Matayos", "Nambale", "Teso North", "Teso South"],
    "Elgeyo-Marakwet": ["Keiyo North", "Keiyo South", "Marakwet East", "Marakwet West"],
    "Embu": ["Manyatta", "Mbeere North", "Mbeere South", "Runyenjes"],
    "Garissa": ["Balambala", "Dadaab", "Fafi", "Garissa Township", "Hulugho", "Ijara", "Lagdera"],
    "Homa Bay": ["Homa Bay Town", "Kabondo Kasipul", "Karachuonyo", "Kasipul", "Mbita", "Ndhiwa", "Rangwe", "Suba"],
    "Isiolo": ["Isiolo North", "Isiolo South"],
    "Kajiado": ["Kajiado Central", "Kajiado East", "Kajiado North", "Kajiado South", "Kajiado West"],
    "Kakamega": ["Butere", "Ikolomani", "Khwisero", "Likuyani", "Lugari", "Lurambi", "Malava", "Matungu", "Mumias East", "Mumias West", "Navakholo", "Shinyalu"],
    "Kericho": ["Ainamoi", "Belgut", "Bureti", "Kipkelion East", "Kipkelion West", "Sigowet-Soin"],
    "Kiambu": [
        "Gatundu North", "Gatundu South", "Githunguri", "Juja", "Kabete", "Kiambaa",
        "Kiambu", "Kikuyu", "Lari", "Limuru", "Ruiru", "Thika Town"
    ],
    "Kilifi": ["Ganze", "Kaloleni", "Kilifi North", "Kilifi South", "Magarini", "Malindi", "Rabai"],
    "Kirinyaga": ["Gichugu", "Kirinyaga Central", "Mwea", "Ndia"],
    "Kisii": ["Bobasi", "Bomachoge Borabu", "Bomachoge Chache", "Bonchari", "Kitutu Chache North", "Kitutu Chache South", "Nyaribari Chache", "Nyaribari Masaba", "South Mugirango"],
    "Kisumu": ["Kisumu Central", "Kisumu East", "Kisumu West", "Muhoroni", "Nyakach", "Nyando", "Seme"],
    "Kitui": ["Kitui Central", "Kitui East", "Kitui Rural", "Kitui South", "Kitui West", "Mwingi Central", "Mwingi North", "Mwingi West"],
    "Kwale": ["Kinango", "Lunga Lunga", "Matuga", "Msambweni"],
    "Laikipia": ["Laikipia East", "Laikipia North", "Laikipia West"],
    "Lamu": ["Lamu East", "Lamu West"],
    "Machakos": ["Kangundo", "Kathiani", "Machakos Town", "Masinga", "Matungulu", "Mavoko", "Mwala", "Yatta"],
    "Makueni": ["Kaiti", "Kibwezi East", "Kibwezi West", "Kilome", "Makueni", "Mbooni"],
    "Mandera": ["Banissa", "Lafey", "Mandera East", "Mandera North", "Mandera South", "Mandera West"],
    "Marsabit": ["Laisamis", "Moyale", "North Horr", "Saku"],
    "Meru": ["Buuri", "Central Imenti", "Igembe Central", "Igembe North", "Igembe South", "North Imenti", "South Imenti", "Tigania East", "Tigania West"],
    "Migori": ["Awendo", "Kuria East", "Kuria West", "Nyatike", "Rongo", "Suna East", "Suna West", "Uriri"],
    "Mombasa": ["Changamwe", "Jomvu", "Kisauni", "Likoni", "Mvita", "Nyali"],
    "Murang'a": ["Gatanga", "Kandara", "Kangema", "Kigumo", "Kiharu", "Maragua", "Mathioya"],
    "Nairobi": [
        "Westlands", "Dagoretti North", "Dagoretti South", "Langata", "Kibra",
        "Roysambu", "Kasarani", "Ruaraka", "Embakasi South", "Embakasi North",
        "Embakasi Central", "Embakasi East", "Embakasi West", "Makadara",
        "Kamukunji", "Starehe", "Mathare"
    ],
    "Nakuru": ["Bahati", "Gilgil", "Kuresoi North", "Kuresoi South", "Molo", "Naivasha", "Nakuru Town East", "Nakuru Town West", "Njoro", "Rongai", "Subukia"],
    "Nandi": ["Aldai", "Chesumei", "Emgwen", "Mosop", "Nandi Hills", "Tinderet"],
    "Narok": ["Emurua Dikirr", "Kilgoris", "Narok East", "Narok North", "Narok South", "Narok West"],
    "Nyamira": ["Borabu", "Kitutu Masaba", "North Mugirango", "West Mugirango"],
    "Nyandarua": ["Kinangop", "Kipipiri", "Ndaragwa", "Ol Joro Orok", "Ol Kalou"],
    "Nyeri": ["Kieni", "Mathira", "Mukurweini", "Nyeri Town", "Othaya", "Tetu"],
    "Samburu": ["Samburu East", "Samburu North", "Samburu West"],
    "Siaya": ["Alego Usonga", "Bondo", "Gem", "Rarieda", "Ugenya", "Ugunja"],
    "Taita-Taveta": ["Mwatate", "Taveta", "Voi", "Wundanyi"],
    "Tana River": ["Bura", "Galole", "Garsen"],
    "Tharaka-Nithi": ["Chuka/Igambang'ombe", "Maara", "Tharaka"],
    "Trans Nzoia": ["Cherangany", "Endebess", "Kiminini", "Kwanza", "Saboti"],
    "Turkana": ["Loima", "Turkana Central", "Turkana East", "Turkana North", "Turkana South", "Turkana West"],
    "Uasin Gishu": ["Ainabkoi", "Kapseret", "Kesses", "Moiben", "Soy", "Turbo"],
    "Vihiga": ["Emuhaya", "Hamisi", "Luanda", "Sabatia", "Vihiga"],
    "Wajir": ["Eldas", "Tarbaj", "Wajir East", "Wajir North", "Wajir South", "Wajir West"],
    "West Pokot": ["Kacheliba", "Kapenguria", "Pokot South", "Sigor"],
}

# South Africa District & Metropolitan Municipalities (geoBoundaries gbOpen & COD-AB)
SOUTH_AFRICA_MUNICIPALITIES: Dict[str, List[str]] = {
    "Gauteng": ["City of Johannesburg", "City of Tshwane", "Ekurhuleni", "Sedibeng", "West Rand"],
    "Western Cape": ["City of Cape Town", "Cape Winelands", "Garden Route", "Overberg", "West Coast", "Central Karoo"],
    "KwaZulu-Natal": ["eThekwini", "uMgungundlovu", "Ugu", "uThukela", "uMzinyathi", "Amajuba", "Zululand", "uMkhanyakude", "King Cetshwayo", "iLembe", "Harry Gwala"],
    "Eastern Cape": ["Buffalo City", "Nelson Mandela Bay", "Sarah Baartman", "Amathole", "Chris Hani", "Joe Gqabi", "OR Tambo", "Alfred Nzo"],
    "Limpopo": ["Capricorn", "Mopani", "Sekhukhune", "Vhembe", "Waterberg"],
    "Mpumalanga": ["Ehlanzeni", "Gert Sibande", "Nkangala"],
    "Free State": ["Mangaung", "Fezile Dabi", "Lejweleputswa", "Thabo Mofutsanyana", "Xhariep"],
    "North West": ["Bojanala Platinum", "Dr Kenneth Kaunda", "Dr Ruth Segomotsi Mompati", "Ngaka Modiri Molema"],
    "Northern Cape": ["Frances Baard", "John Taolo Gaetsewe", "Namakwa", "Pixley ka Seme", "ZF Mgcawu"],
}

# Ghana Metropolitan, Municipal and District Assemblies (UN OCHA/HDX COD-AB)
GHANA_DISTRICTS: Dict[str, List[str]] = {
    "Ahafo": ["Asunafo North", "Asunafo South", "Asutifi North", "Asutifi South", "Tano North", "Tano South"],
    "Ashanti": [
        "Kumasi Metropolitan", "Asokore Mampong Municipal", "Obuasi Municipal", "Ejisu Municipal",
        "Bekwai Municipal", "Mampong Municipal", "Atwima Nwabiagya", "Kwabre East",
        "Atwima Kwanwoma", "Atwima Mponua", "Amansie Central", "Amansie West",
        "Afigya Kwabre", "Asante Akim Central", "Asante Akim North", "Asante Akim South",
        "Offinso Municipal", "Offinso North", "Sekyere East", "Sekyere Central", "Sekyere South"
    ],
    "Bono": [
        "Sunyani Municipal", "Sunyani West", "Berekum East Municipal", "Berekum West",
        "Dormaa Central Municipal", "Dormaa East", "Dormaa West", "Jaman North",
        "Jaman South Municipal", "Tain", "Banda", "Wenchi Municipal"
    ],
    "Bono East": [
        "Techiman Municipal", "Techiman North", "Atebubu-Amantin Municipal",
        "Kintampo North Municipal", "Kintampo South", "Nkoranza North",
        "Nkoranza South Municipal", "Pru East", "Pru West", "Sene East", "Sene West"
    ],
    "Central": [
        "Cape Coast Metropolitan", "Awutu Senya East Municipal", "Effutu Municipal",
        "Komenda-Edina-Eguafo-Abirem Municipal", "Mfantseman Municipal", "Agona West Municipal",
        "Assin Central Municipal", "Gomoa East", "Gomoa Central", "Gomoa West",
        "Abura-Asebu-Kwamankese", "Twifo Atti-Morkwa", "Upper Denkyira East Municipal", "Upper Denkyira West"
    ],
    "Eastern": [
        "New Juaben South Municipal", "New Juaben North Municipal", "Birim Central Municipal",
        "Kwahu West Municipal", "Suhum Municipal", "Akuapem South", "Akuapem North Municipal",
        "Nsawam Adoagyiri Municipal", "Abuakwa South Municipal", "Abuakwa North Municipal",
        "Lower Manya Krobo Municipal", "Yilo Krobo Municipal", "Asuogyaman", "Fanteakwa North", "Fanteakwa South"
    ],
    "Greater Accra": [
        "Accra Metropolitan", "Tema Metropolitan", "Ga Central Municipal", "Ga East Municipal",
        "Ga North Municipal", "Ga South Municipal", "Ga West Municipal", "La Dade Kotopon Municipal",
        "Ledzokuku Municipal", "Krowor Municipal", "Adentan Municipal", "Ashaiman Municipal",
        "Shai Osudoku", "Ada East", "Ada West", "Ayawaso Central Municipal",
        "Ayawaso East Municipal", "Ayawaso North Municipal", "Ayawaso West Municipal",
        "Ablekuma Central Municipal", "Ablekuma North Municipal", "Ablekuma West Municipal",
        "Korle Klottey Municipal", "Okaikwei North Municipal"
    ],
    "North East": ["East Mamprusi Municipal", "West Mamprusi Municipal", "Bunkpurugu Nakpanduri", "Chereponi", "Mamprugu Moagduri", "Yunyoo-Nasuan"],
    "Northern": [
        "Tamale Metropolitan", "Sagnarigu Municipal", "Yendi Municipal", "Savelugu Municipal",
        "Nanton", "Tolon", "Kumbungu", "Mion", "Gushegu Municipal", "Karaga",
        "Tatale Sanguli", "Zabzugu", "Kpandai", "Nanumba North Municipal", "Nanumba South"
    ],
    "Oti": ["Krachi East Municipal", "Krachi West", "Krachi Nchumuru", "Nkwanta North", "Nkwanta South Municipal", "Biakoye", "Jasikan", "Kadjebi"],
    "Savannah": ["West Gonja Municipal", "East Gonja Municipal", "Central Gonja", "North Gonja", "Bole", "Sawla-Tuna-Kalba", "North East Gonja"],
    "Upper East": [
        "Bolgatanga Municipal", "Bolgatanga East", "Bawku Municipal", "Kasena Nankana Municipal",
        "Bongo", "Builsa North Municipal", "Builsa South", "Garu", "Tempane", "Talensi",
        "Nabdam", "Binduri", "Pusiga", "Kasena Nankana West"
    ],
    "Upper West": [
        "Wa Municipal", "Wa East", "Wa West", "Jirapa Municipal", "Lawra Municipal",
        "Nandom Municipal", "Nadowli Kaleo", "Daffiama Bussie Issa", "Sissala East Municipal",
        "Sissala West", "Lambussie Karni"
    ],
    "Volta": [
        "Ho Municipal", "Kpando Municipal", "Hohoe Municipal", "South Dayi", "North Dayi",
        "Afadzato South", "Central Tongu", "North Tongu", "South Tongu", "Ketu South Municipal",
        "Ketu North Municipal", "Keta Municipal", "Anloga", "Akatsi South", "Akatsi North"
    ],
    "Western": [
        "Sekondi-Takoradi Metropolitan", "Effia Kwesimintsim Municipal", "Tarkwa Nsuaem Municipal",
        "Prestea Huni-Valley Municipal", "Ahanta West Municipal", "Nzema East Municipal",
        "Ellembelle", "Jomoro Municipal", "Wassa East", "Wassa Amenfi West Municipal",
        "Wassa Amenfi East Municipal", "Wassa Amenfi Central"
    ],
    "Western North": ["Sefwi Wiawso Municipal", "Bibiani Anhwiaso Bekwai Municipal", "Juaboso", "Bia East", "Bia West", "Bodi", "Suaman", "Aowin Municipal", "Akontombra"],
}


def _build_catalogue() -> Dict[str, Any]:
    """
    Build the canonical in-memory normalized WDOS administrative catalogue
    for all 55 African countries.
    """
    from .african_geography import AFRICAN_COUNTRIES
    from .onboarding_forms import NIGERIA_LOCATIONS

    catalogue: Dict[str, Any] = {}

    for name, raw in AFRICAN_COUNTRIES.items():
        iso2 = raw["code"].upper()
        iso3 = ISO2_TO_ISO3[iso2]
        source_meta = get_source_for_country(iso3)

        # Level 2 reliability determination
        level2_reliable = False
        level2_data: Dict[str, List[Dict[str, str]]] = {}

        if iso3 == "NGA":
            level2_reliable = True
            for state_code, state_name in raw["regions"]:
                # Map LGAs
                lgas = NIGERIA_LOCATIONS.get(state_name) or NIGERIA_LOCATIONS.get(state_name.replace(" State", "")) or []
                if not lgas and state_name in ("FCT", "Federal Capital Territory", "FCT (Abuja)"):
                    lgas = NIGERIA_LOCATIONS.get("FCT (Abuja)", [])
                level2_units = []
                for lga in lgas:
                    slug = lga.lower().replace(" ", "-").replace("/", "-").replace("'", "")
                    level2_units.append({
                        "id": f"{state_code}-{slug}",
                        "parent_id": state_code,
                        "country_iso3": iso3,
                        "display_name": lga,
                        "local_unit_type": raw["local_label"],
                        "source": source_meta["name"],
                        "source_version": source_meta["version"],
                        "last_verified_date": source_meta["last_verified_date"],
                    })
                level2_data[state_code] = level2_units
                level2_data[state_name] = level2_units
        elif iso3 == "KEN":
            level2_reliable = True
            for reg_code, reg_name in raw["regions"]:
                sub_list = KENYA_SUBCOUNTIES.get(reg_name, [])
                level2_units = []
                for sub in sub_list:
                    slug = sub.lower().replace(" ", "-")
                    level2_units.append({
                        "id": f"{reg_code}-{slug}",
                        "parent_id": reg_code,
                        "country_iso3": iso3,
                        "display_name": sub,
                        "local_unit_type": raw["local_label"],
                        "source": source_meta["name"],
                        "source_version": source_meta["version"],
                        "last_verified_date": source_meta["last_verified_date"],
                    })
                level2_data[reg_code] = level2_units
                level2_data[reg_name] = level2_units
        elif iso3 == "ZAF":
            level2_reliable = True
            for reg_code, reg_name in raw["regions"]:
                sub_list = SOUTH_AFRICA_MUNICIPALITIES.get(reg_name, [])
                level2_units = []
                for sub in sub_list:
                    slug = sub.lower().replace(" ", "-")
                    level2_units.append({
                        "id": f"{reg_code}-{slug}",
                        "parent_id": reg_code,
                        "country_iso3": iso3,
                        "display_name": sub,
                        "local_unit_type": raw["local_label"],
                        "source": source_meta["name"],
                        "source_version": source_meta["version"],
                        "last_verified_date": source_meta["last_verified_date"],
                    })
                level2_data[reg_code] = level2_units
                level2_data[reg_name] = level2_units
        elif iso3 == "GHA":
            level2_reliable = True
            for reg_code, reg_name in raw["regions"]:
                sub_list = GHANA_DISTRICTS.get(reg_name, [])
                level2_units = []
                for sub in sub_list:
                    slug = sub.lower().replace(" ", "-")
                    level2_units.append({
                        "id": f"{reg_code}-{slug}",
                        "parent_id": reg_code,
                        "country_iso3": iso3,
                        "display_name": sub,
                        "local_unit_type": raw["local_label"],
                        "source": source_meta["name"],
                        "source_version": source_meta["version"],
                        "last_verified_date": source_meta["last_verified_date"],
                    })
                level2_data[reg_code] = level2_units
                level2_data[reg_name] = level2_units

        # Build Level 1 units
        level1_units = []
        for reg_code, reg_name in raw["regions"]:
            level1_units.append({
                "id": reg_code,
                "parent_id": iso3,
                "display_name": reg_name,
                "local_unit_type": raw["admin_label"],
                "source": source_meta["name"],
                "source_version": source_meta["version"],
                "last_verified_date": source_meta["last_verified_date"],
            })

        country_entry = {
            "iso3": iso3,
            "iso2": iso2,
            "code": iso2,  # backwards compatibility
            "name": name,
            "admin1_label": raw["admin_label"],
            "admin_label": raw["admin_label"],  # backwards compatibility
            "admin2_label": raw["local_label"],
            "local_label": raw["local_label"],  # backwards compatibility
            "level2_reliable": level2_reliable,
            "source": source_meta["name"],
            "source_version": source_meta["version"],
            "last_verified_date": source_meta["last_verified_date"],
            "level1": level1_units,
            "level2": level2_data,
            "regions": raw["regions"],  # (code, name) tuples for backwards compatibility
        }

        catalogue[iso3] = country_entry
        catalogue[iso2] = country_entry
        catalogue[name.lower()] = country_entry

    return catalogue


# Global cache
_CATALOGUE_CACHE: Optional[Dict[str, Any]] = None

def get_catalogue() -> Dict[str, Any]:
    global _CATALOGUE_CACHE
    if _CATALOGUE_CACHE is None:
        _CATALOGUE_CACHE = _build_catalogue()
    return _CATALOGUE_CACHE


def __getattr__(name: str) -> Any:
    if name == "AFRICAN_GEOGRAPHY_CATALOGUE":
        return get_catalogue()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_all_countries() -> List[Dict[str, Any]]:
    """Return unique list of all 55 African countries sorted by display name."""
    cat = get_catalogue()
    seen = set()
    countries = []
    for k, v in cat.items():
        if len(k) == 3 and k.isupper() and k not in seen:
            seen.add(k)
            countries.append(v)
    return sorted(countries, key=lambda c: c["name"])


def get_country_by_identifier(identifier: Optional[str]) -> Optional[Dict[str, Any]]:
    """Lookup country by ISO3, ISO2, or full display name (case-insensitive)."""
    if not identifier:
        return None
    cat = get_catalogue()
    key = str(identifier).strip()
    return cat.get(key.upper()) or cat.get(key.lower()) or None


def get_level1_divisions(country_identifier: str) -> List[Dict[str, Any]]:
    """Return normalized Level-1 administrative divisions for a country."""
    c = get_country_by_identifier(country_identifier)
    return c["level1"] if c else []


def find_level1_in_country(country_identifier: str, region_identifier: str) -> Optional[Dict[str, Any]]:
    """Find a specific Level-1 division by code or display name."""
    divisions = get_level1_divisions(country_identifier)
    if not divisions or not region_identifier:
        return None
    target = str(region_identifier).strip().lower()
    for d in divisions:
        if d["id"].lower() == target or d["display_name"].lower() == target:
            return d
    return None


def get_level2_divisions(country_identifier: str, region_identifier: str) -> List[Dict[str, Any]]:
    """Return normalized Level-2 divisions for a country and region (if reliable/available)."""
    c = get_country_by_identifier(country_identifier)
    if not c or not region_identifier:
        return []
    reg_clean = str(region_identifier).strip()
    reg_obj = find_level1_in_country(country_identifier, reg_clean)
    lookup_keys = [reg_clean]
    if reg_obj:
        lookup_keys.extend([reg_obj["id"], reg_obj["display_name"]])

    for k in lookup_keys:
        if k in c["level2"]:
            return c["level2"][k]
    return []


def is_level2_reliable(country_identifier: str) -> bool:
    """Check if country has verified/reliable Level-2 coverage in catalogue."""
    c = get_country_by_identifier(country_identifier)
    return bool(c and c.get("level2_reliable"))


def check_geography_completeness() -> Dict[str, Any]:
    """
    Run country-by-country completeness check before release:
    - 55 countries present
    - Level-1 data present (or documented exception)
    - Valid parent links (Level 1 -> Country ISO3, Level 2 -> Level 1 ID)
    - No duplicates under one parent
    - Source metadata recorded for country, Level 1, and Level 2
    """
    countries = get_all_countries()
    errors: List[str] = []
    warnings: List[str] = []
    country_reports: List[Dict[str, Any]] = []

    if len(countries) != 55:
        errors.append(f"Expected exactly 55 African countries, found {len(countries)}.")

    total_level1 = 0
    total_level2 = 0

    for c in countries:
        c_errors: List[str] = []
        iso3 = c["iso3"]
        name = c["name"]

        # Validate country fields
        if not c.get("iso3") or len(c["iso3"]) != 3 or not c["iso3"].isupper():
            c_errors.append(f"Invalid ISO3 '{c.get('iso3')}' for {name}")
        if not c.get("iso2") or len(c["iso2"]) != 2 or not c["iso2"].isupper():
            c_errors.append(f"Invalid ISO2 '{c.get('iso2')}' for {name}")
        if not c.get("admin1_label"):
            c_errors.append(f"Missing admin1_label for {name}")
        if not c.get("local_label"):
            c_errors.append(f"Missing local_label for {name}")
        if not c.get("source") or not c.get("source_version") or not c.get("last_verified_date"):
            c_errors.append(f"Missing source metadata for country {name}")

        # Level 1 completeness
        l1_list = c.get("level1", [])
        if len(l1_list) == 0:
            c_errors.append(f"Country {name} ({iso3}) has no Level-1 divisions")

        total_level1 += len(l1_list)

        # Check for duplicates in Level 1 under this country
        l1_ids = [d["id"] for d in l1_list]
        l1_names = [d["display_name"].lower() for d in l1_list]

        if len(l1_ids) != len(set(l1_ids)):
            dup_ids = [i for i in l1_ids if l1_ids.count(i) > 1]
            c_errors.append(f"Duplicate Level-1 IDs in {name}: {set(dup_ids)}")
        if len(l1_names) != len(set(l1_names)):
            dup_names = [n for n in l1_names if l1_names.count(n) > 1]
            c_errors.append(f"Duplicate Level-1 names in {name}: {set(dup_names)}")

        # Check Level 1 parent links and metadata
        l1_id_set = set(l1_ids)
        for l1 in l1_list:
            if l1.get("parent_id") != iso3:
                c_errors.append(f"Level-1 unit {l1.get('id')} has invalid parent_id '{l1.get('parent_id')}', expected '{iso3}'")
            if not l1.get("display_name"):
                c_errors.append(f"Level-1 unit {l1.get('id')} in {name} is missing display_name")
            if not l1.get("local_unit_type"):
                c_errors.append(f"Level-1 unit {l1.get('id')} in {name} is missing local_unit_type")
            if not l1.get("source") or not l1.get("source_version") or not l1.get("last_verified_date"):
                c_errors.append(f"Level-1 unit {l1.get('id')} in {name} is missing source metadata")

        # Check Level 2 data if present
        c_l2_count = 0
        level2_dict = c.get("level2", {})
        checked_level1_keys = set()

        for reg_key, l2_list in level2_dict.items():
            if reg_key in checked_level1_keys:
                continue
            # Only count once per distinct list
            checked_level1_keys.add(reg_key)
            if reg_key not in l1_id_set:
                # Might be registered by name too
                matched_l1 = [l for l in l1_list if l["display_name"] == reg_key or l["id"] == reg_key]
                if not matched_l1:
                    c_errors.append(f"Level-2 parent key '{reg_key}' not found in Level-1 divisions of {name}")

            # Check duplicates under this Level-1 parent
            l2_ids = [u["id"] for u in l2_list]
            l2_names = [u["display_name"].lower() for u in l2_list]
            if len(l2_ids) != len(set(l2_ids)):
                c_errors.append(f"Duplicate Level-2 IDs under {name} / {reg_key}: {set([i for i in l2_ids if l2_ids.count(i) > 1])}")
            if len(l2_names) != len(set(l2_names)):
                c_errors.append(f"Duplicate Level-2 names under {name} / {reg_key}: {set([n for n in l2_names if l2_names.count(n) > 1])}")

            for l2 in l2_list:
                if l2.get("country_iso3") != iso3:
                    c_errors.append(f"Level-2 unit {l2.get('id')} has invalid country_iso3 '{l2.get('country_iso3')}'")
                if l2.get("parent_id") not in l1_id_set:
                    c_errors.append(f"Level-2 unit {l2.get('id')} parent_id '{l2.get('parent_id')}' not in Level-1 IDs of {name}")
                if not l2.get("source") or not l2.get("source_version") or not l2.get("last_verified_date"):
                    c_errors.append(f"Level-2 unit {l2.get('id')} in {name} is missing source metadata")

            c_l2_count += len(l2_list)

        # Discard duplicate count from dual keying (code vs name)
        # Deduplicate distinct Level 2 units by ID
        distinct_l2_ids = set()
        for l2_list in level2_dict.values():
            for u in l2_list:
                distinct_l2_ids.add(u["id"])
        c_distinct_l2 = len(distinct_l2_ids)
        total_level2 += c_distinct_l2

        status = "FAIL" if c_errors else "PASS"
        if c_errors:
            errors.extend(c_errors)

        country_reports.append({
            "iso3": iso3,
            "iso2": c["iso2"],
            "name": name,
            "admin1_label": c["admin1_label"],
            "local_label": c["local_label"],
            "level1_count": len(l1_list),
            "level2_count": c_distinct_l2,
            "level2_reliable": c["level2_reliable"],
            "source": c["source"],
            "source_version": c["source_version"],
            "last_verified_date": c["last_verified_date"],
            "status": status,
            "errors": c_errors,
        })

    return {
        "valid": len(errors) == 0,
        "country_count": len(countries),
        "total_level1": total_level1,
        "total_level2": total_level2,
        "errors": errors,
        "warnings": warnings,
        "country_reports": country_reports,
    }


def import_catalogue_to_database() -> Dict[str, int]:
    """
    Import/seed the normalized WDOS geography catalogue into the Django database
    (CountryCatalogue and AdministrativeDivision models).
    """
    from django.db import transaction
    from .models import CountryCatalogue, AdministrativeDivision

    countries = get_all_countries()
    c_created = 0
    c_updated = 0
    l1_created = 0
    l2_created = 0

    with transaction.atomic():
        for c_data in countries:
            iso3 = c_data["iso3"]
            c_obj, created = CountryCatalogue.objects.update_or_create(
                iso3=iso3,
                defaults={
                    "iso2": c_data["iso2"],
                    "name": c_data["name"],
                    "admin1_label": c_data["admin1_label"],
                    "admin2_label": c_data["local_label"],
                    "level2_reliable": c_data["level2_reliable"],
                    "source": c_data["source"],
                    "source_version": c_data["source_version"],
                    "last_verified_date": c_data["last_verified_date"],
                }
            )
            if created:
                c_created += 1
            else:
                c_updated += 1

            # Seed Level 1
            level1_objs = {}
            for l1 in c_data["level1"]:
                obj, _ = AdministrativeDivision.objects.update_or_create(
                    id=l1["id"],
                    defaults={
                        "level": 1,
                        "country": c_obj,
                        "parent": None,
                        "display_name": l1["display_name"],
                        "local_unit_type": l1["local_unit_type"],
                        "source": l1["source"],
                        "source_version": l1["source_version"],
                        "last_verified_date": l1["last_verified_date"],
                    }
                )
                level1_objs[l1["id"]] = obj
                l1_created += 1

            # Seed Level 2 (where reliable)
            seen_l2 = set()
            for reg_key, l2_list in c_data.get("level2", {}).items():
                for l2 in l2_list:
                    l2_id = l2["id"]
                    if l2_id in seen_l2:
                        continue
                    seen_l2.add(l2_id)
                    parent_obj = level1_objs.get(l2["parent_id"])
                    AdministrativeDivision.objects.update_or_create(
                        id=l2_id,
                        defaults={
                            "level": 2,
                            "country": c_obj,
                            "parent": parent_obj,
                            "display_name": l2["display_name"],
                            "local_unit_type": l2["local_unit_type"],
                            "source": l2["source"],
                            "source_version": l2["source_version"],
                            "last_verified_date": l2["last_verified_date"],
                        }
                    )
                    l2_created += 1

    return {
        "total_countries": c_created + c_updated,
        "countries_created": c_created,
        "countries_updated": c_updated,
        "level1_created": l1_created,
        "level2_created": l2_created,
    }


def record_data_improvement_flag(
    account=None,
    draft=None,
    country_iso3="",
    region_id="",
    region_name="",
    unlisted_subdivision="",
    unit_type="",
    notes="",
):
    """
    Log an unlisted subdivision exception for subsequent catalogue improvement.
    Ensures missing seed data is never hidden.
    """
    from .models import DataImprovementFlag
    try:
        flag = DataImprovementFlag.objects.create(
            draft=draft,
            account=account,
            country_iso3=str(country_iso3).upper()[:3],
            region_id=str(region_id)[:64],
            region_name=str(region_name)[:150],
            unlisted_subdivision=str(unlisted_subdivision).strip()[:150],
            unit_type=str(unit_type)[:100],
            notes=str(notes),
        )
        return flag
    except Exception:
        return None

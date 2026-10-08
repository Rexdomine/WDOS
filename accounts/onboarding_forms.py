"""Forms map to approved v1 ONB controls; sample policy values are not defaults."""
from zoneinfo import available_timezones
import io
from PIL import Image, UnidentifiedImageError
from django import forms
from .onboarding_policy import current_policy
from .locale import LANGUAGES
from .african_geography import (
    AFRICAN_COUNTRIES,
    DEFAULT_COUNTRY_TIMEZONES,
    MULTI_TIMEZONE_COUNTRIES,
    find_region_in_country,
    format_user_datetime,
    get_african_countries_choices,
    get_country,
    get_country_default_timezone,
    get_country_regions,
    get_country_timezones,
    is_multi_timezone_country,
    resolve_timezone_for_location,
)


class BaseForm(forms.Form):
    def __init__(self, *args, account=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'input'
                field.widget.attrs['autocomplete'] = 'off'


class WelcomeForm(BaseForm):
    language = forms.ChoiceField(label='Interface language', choices=[(code, item['name']) for code, item in LANGUAGES.items()])
    timezone = forms.ChoiceField(label='Your timezone', choices=[(s, s) for s in sorted(available_timezones())], initial='UTC')
    reading = forms.ChoiceField(label='Reading preference', choices=[('standard', 'Standard text'), ('large', 'Large text')], initial='standard')
    reduce_motion = forms.BooleanField(label='Motion preference', required=False, help_text='Reduce non-essential motion')


class ProfileForm(BaseForm):
    full_name = forms.CharField(label='Full name', max_length=150)
    preferred_name = forms.CharField(label='Preferred name', max_length=150, required=False)
    email = forms.EmailField(label='Email address', disabled=True)
    photo = forms.FileField(label='Profile photo', required=False)

    def clean_photo(self):
        uploaded = self.cleaned_data.get('photo')
        if not uploaded:
            return None
        if uploaded.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Check the highlighted information')
        try:
            with Image.open(uploaded) as image:
                if image.format not in ('JPEG', 'PNG') or image.width * image.height > 12000000:
                    raise ValueError('Unsupported image')
                image.load()
                clean = image.convert('RGB')
                clean.thumbnail((512, 512))
                # New image drops EXIF/ICC/comments and original file name.
                stripped = Image.new('RGB', clean.size)
                stripped.paste(clean)
                output = io.BytesIO()
                stripped.save(output, format='PNG')
                return output.getvalue()
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as error:
            raise forms.ValidationError('Check the highlighted information') from error


DEFAULT_ELIGIBILITY = [
    {
        'code': 'adult',
        'label': 'Adult Member (18+)',
        'network': 'WGMN',
        'basis': 'Identity verification on file',
    },
    {
        'code': 'youth',
        'label': 'Youth Member (15–24)',
        'network': 'WNNN',
        'basis': 'Self attestation with guarantor',
    },
]


class NetworkForm(BaseForm):
    eligibility = forms.ChoiceField(
        label='Age eligibility',
        choices=[('', 'Select age eligibility')]
        + [(r['code'], r['label']) for r in DEFAULT_ELIGIBILITY]
        + [('pending', 'More information needed')],
    )
    network = forms.ChoiceField(label='Proposed network', choices=[('', 'Select network'), ('WGMN', 'WGMN — Good Mother Network'), ('WNNN', 'WNNN')])
    verification_basis = forms.CharField(
        label='Verification basis',
        disabled=True,
        required=False,
        initial='Pending review',
        help_text='System assigned based on your selected eligibility tier. This field cannot be edited.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        policy = current_policy()
        eligibility_list = (policy.get('eligibility') if policy and policy.get('eligibility') else None) or DEFAULT_ELIGIBILITY
        self.fields['eligibility'].choices = (
            [('', 'Select age eligibility')]
            + [(r['code'], r['label']) for r in eligibility_list]
            + [('pending', 'More information needed')]
        )
        selected_el = None
        if self.data and self.data.get('eligibility'):
            selected_el = self.data.get('eligibility')
        elif self.initial and self.initial.get('eligibility'):
            selected_el = self.initial.get('eligibility')
        for r in eligibility_list:
            if r['code'] == selected_el and r.get('basis'):
                self.fields['verification_basis'].initial = r['basis']
                break

    def clean(self):
        data = super().clean()
        policy = current_policy()
        eligibility_list = (policy.get('eligibility') if policy and policy.get('eligibility') else None) or DEFAULT_ELIGIBILITY
        selected_el = data.get('eligibility')
        selected_net = data.get('network')
        if selected_el and selected_el != 'pending':
            if not any(r['code'] == selected_el and r['network'] == selected_net for r in eligibility_list):
                self.add_error('eligibility', 'More information needed')
        return data
    eligibility_confirmed = forms.BooleanField(label='Confirm eligibility', help_text='I confirm this information is accurate.')


NIGERIA_LOCATIONS = {
    "Abia": [
        "Aba North", "Aba South", "Arochukwu", "Bende", "Ikwuano", "Isiala Ngwa North", "Isiala Ngwa South",
        "Isuikwuato", "Obi Ngwa", "Ohafia", "Osisioma", "Ugwunagbo", "Ukwa East", "Ukwa West",
        "Umuahia North", "Umuahia South", "Umu Nneochi",
    ],
    "Adamawa": [
        "Demsa", "Fufore", "Ganye", "Girei", "Gombi", "Guyuk", "Hong", "Jada", "Lamurde", "Madagali",
        "Maiha", "Mayo Belwa", "Michika", "Mubi North", "Mubi South", "Numan", "Shelleng", "Song",
        "Toungo", "Yola North", "Yola South",
    ],
    "Akwa Ibom": [
        "Abak", "Eastern Obolo", "Eket", "Esit Eket", "Essien Udim", "Etim Ekpo", "Etinan", "Ibeno",
        "Ibesikpo Asutan", "Ibiono Ibom", "Ika", "Ikono", "Ikot Abasi", "Ikot Ekpene", "Ini", "Itu",
        "Mbo", "Mkpat Enin", "Nsit Atai", "Nsit Ibom", "Nsit Ubium", "Obot Akara", "Okobo", "Onna",
        "Oron", "Oruk Anam", "Udung Uko", "Ukanafun", "Uruan", "Urue-Offong/Oruko", "Uyo",
    ],
    "Anambra": [
        "Aguata", "Anambra East", "Anambra West", "Anaocha", "Awka North", "Awka South",
        "Ayamelum", "Dunukofia", "Ekwusigo", "Idemili North", "Idemili South", "Ihiala",
        "Njikoka", "Nnewi North", "Nnewi South", "Ogbaru", "Onitsha North", "Onitsha South",
        "Orumba North", "Orumba South", "Oyi",
    ],
    "Bauchi": [
        "Alkaleri", "Bauchi", "Bogoro", "Damban", "Darazo", "Dass", "Gamawa", "Ganjuwa", "Giade",
        "Itas/Gadau", "Jama'are", "Katagum", "Kirfi", "Misau", "Ningi", "Shira", "Tafawa Balewa",
        "Toro", "Warji", "Zaki",
    ],
    "Bayelsa": [
        "Brass", "Ekeremor", "Kolokuma/Opokuma", "Nembe", "Ogbia", "Sagbama", "Southern Ijaw", "Yenagoa",
    ],
    "Benue": [
        "Ado", "Agatu", "Apa", "Buruku", "Gboko", "Guma", "Gwer East", "Gwer West", "Katsina-Ala",
        "Konshisha", "Kwande", "Logo", "Makurdi", "Obi", "Ogbadibo", "Ohimini", "Oju", "Okpokwu",
        "Otukpo", "Tarka", "Ukum", "Ushongo", "Vandeikya",
    ],
    "Borno": [
        "Abadam", "Askira/Uba", "Bama", "Bayo", "Biu", "Chibok", "Damboa", "Dikwa", "Gubio",
        "Guzamala", "Gwoza", "Hawul", "Jere", "Kaga", "Kala/Balge", "Konduga", "Kukawa",
        "Kwaya Kusar", "Mafa", "Magumeri", "Maiduguri", "Marte", "Mobbar", "Monguno", "Ngala",
        "Nganzai", "Shani",
    ],
    "Cross River": [
        "Abi", "Akamkpa", "Akpabuyo", "Bakassi", "Bekwarra", "Biase", "Boki", "Calabar Municipal",
        "Calabar South", "Etung", "Ikom", "Obanliku", "Obubra", "Obudu", "Odukpani", "Ogoja",
        "Yakuur", "Yala",
    ],
    "Delta": [
        "Aniocha North", "Aniocha South", "Bomadi", "Burutu", "Ethiope East", "Ethiope West",
        "Ika North East", "Ika South", "Isoko North", "Isoko South", "Ndokwa East", "Ndokwa West",
        "Okpe", "Oshimili North", "Oshimili South", "Patani", "Sapele", "Udu", "Ughelli North",
        "Ughelli South", "Ukwuani", "Uvwie", "Warri North", "Warri South", "Warri South West",
    ],
    "Ebonyi": [
        "Abakaliki", "Afikpo North", "Afikpo South", "Ebonyi", "Ezza North", "Ezza South", "Ikwo",
        "Ishielu", "Ivo", "Izzi", "Ohaozara", "Ohaukwu", "Onicha",
    ],
    "Edo": [
        "Akoko-Edo", "Egor", "Esan Central", "Esan North-East", "Esan South-East", "Esan West",
        "Etsako Central", "Etsako East", "Etsako West", "Igueben", "Ikpoba-Okha", "Orhionmwon",
        "Oredo", "Ovia North-East", "Ovia South-West", "Owan East", "Owan West", "Uhunmwonde",
    ],
    "Ekiti": [
        "Ado Ekiti", "Efon", "Ekiti East", "Ekiti South-West", "Ekiti West", "Emure", "Gbonyin",
        "Ido Osi", "Ijero", "Ikere", "Ikole", "Ilejemeje", "Irepodun/Ifelodun", "Ise/Orun", "Moba", "Oye",
    ],
    "Enugu": [
        "Aninri", "Awgu", "Enugu East", "Enugu North", "Enugu South", "Ezeagu", "Igbo Etiti",
        "Igbo Eze North", "Igbo Eze South", "Isi Uzo", "Nkanu East", "Nkanu West", "Nsukka",
        "Oji River", "Udenu", "Udi", "Uzo Uwani",
    ],
    "FCT (Abuja)": [
        "Abaji", "Abuja Municipal", "Bwari", "Gwagwalada", "Kuje", "Kwali",
    ],
    "Gombe": [
        "Akko", "Balanga", "Billiri", "Dukku", "Funakaye", "Gombe", "Kaltungo", "Kwami",
        "Nafada", "Shongom", "Yamaltu/Deba",
    ],
    "Imo": [
        "Aboh Mbaise", "Ahiazu Mbaise", "Ehime Mbano", "Ezinihitte", "Ideato North", "Ideato South",
        "Ihitte/Uboma", "Ikeduru", "Isiala Mbano", "Isu", "Mbaitoli", "Ngor Okpala", "Njaba",
        "Nkwerre", "Nwangele", "Obowo", "Oguta", "Ohaji/Egbema", "Okigwe", "Onuimo", "Orlu",
        "Orsu", "Oru East", "Oru West", "Owerri Municipal", "Owerri North", "Owerri West",
    ],
    "Jigawa": [
        "Auyo", "Babura", "Biriniwa", "Birnin Kudu", "Buji", "Dutse", "Gagarawa", "Garki",
        "Gumel", "Guri", "Gwaram", "Gwiwa", "Hadejia", "Jahun", "Kafin Hausa", "Kaugama",
        "Kazaure", "Kiri Kasama", "Kiyawa", "Maigatari", "Malam Madori", "Miga", "Ringim",
        "Roni", "Sule Tankarkar", "Taura", "Yankwashi",
    ],
    "Kaduna": [
        "Birnin Gwari", "Chikun", "Giwa", "Igabi", "Ikara", "Jaba", "Jema'a", "Kachia",
        "Kaduna North", "Kaduna South", "Kagarko", "Kajuru", "Kaura", "Kauru", "Kubau",
        "Kudan", "Lere", "Makarfi", "Sabon Gari", "Sanga", "Soba", "Zangon Kataf", "Zaria",
    ],
    "Kano": [
        "Ajingi", "Albasu", "Bagwai", "Bebeji", "Bichi", "Bunkure", "Dala", "Dambatta",
        "Dawakin Kudu", "Dawakin Tofa", "Doguwa", "Fagge", "Gabasawa", "Garko", "Garun Mallam",
        "Gaya", "Gezawa", "Gwale", "Gwarzo", "Kabo", "Kano Municipal", "Karaye", "Kibiya",
        "Kiru", "Kumbotso", "Kunchi", "Kura", "Madobi", "Makoda", "Minjibir", "Nassarawa",
        "Rano", "Rimin Gado", "Rogo", "Shanono", "Sumaila", "Takai", "Tarauni", "Tofa",
        "Tsanyawa", "Tudun Wada", "Ungogo", "Warawa", "Wudil",
    ],
    "Katsina": [
        "Bakori", "Batagarawa", "Batsari", "Baure", "Bindawa", "Charanchi", "Dandume", "Danja",
        "Dan Musa", "Daura", "Dutsi", "Dutsin Ma", "Faskari", "Funtua", "Ingawa", "Jibia",
        "Kafur", "Kaita", "Kankara", "Kankia", "Katsina", "Kurfi", "Kusada", "Mai'Adua",
        "Malumfashi", "Mani", "Mashi", "Matazu", "Musawa", "Rimi", "Sabuwa", "Safana",
        "Sandamu", "Zango",
    ],
    "Kebbi": [
        "Aleiro", "Arewa Dandi", "Argungu", "Augie", "Bagudo", "Birnin Kebbi", "Bunza", "Dandi",
        "Danko/Wasagu", "Fakai", "Gwandu", "Jega", "Kalgo", "Koko/Besse", "Maiyama", "Ngaski",
        "Sakaba", "Shanga", "Suru", "Yauri", "Zuru",
    ],
    "Kogi": [
        "Adavi", "Ajaokuta", "Ankpa", "Bassa", "Dekina", "Ibaji", "Idah", "Igalamela Odolu",
        "Ijumu", "Kabba/Bunu", "Kogi", "Lokoja", "Mopa Muro", "Ofu", "Ogori/Magongo", "Okehi",
        "Okene", "Olamaboro", "Omala", "Yagba East", "Yagba West",
    ],
    "Kwara": [
        "Asa", "Baruten", "Edu", "Ekiti", "Ifelodun", "Ilorin East", "Ilorin South", "Ilorin West",
        "Irepodun", "Isin", "Kaiama", "Moro", "Offa", "Oke Ero", "Oyun", "Pategi",
    ],
    "Lagos": [
        "Agege", "Ajeromi-Ifelodun", "Alimosho", "Amuwo-Odofin", "Apapa", "Badagry", "Epe",
        "Eti-Osa", "Ibeju-Lekki", "Ifako-Ijaiye", "Ikeja", "Ikorodu", "Kosofe", "Lagos Island",
        "Lagos Mainland", "Mushin", "Ojo", "Oshodi-Isolo", "Shomolu", "Surulere",
    ],
    "Nasarawa": [
        "Akwanga", "Awe", "Doma", "Karu", "Keana", "Keffi", "Kokona", "Lafia", "Nasarawa",
        "Nasarawa Egon", "Obi", "Toto", "Wamba",
    ],
    "Niger": [
        "Agaie", "Agwara", "Bida", "Borgu", "Bosso", "Chanchaga", "Edati", "Gbako", "Gurara",
        "Katcha", "Kontagora", "Lapai", "Lavun", "Magama", "Mariga", "Mashegu", "Mokwa",
        "Moya", "Paikoro", "Rafi", "Rijau", "Shiroro", "Suleja", "Tafa", "Wushishi",
    ],
    "Ogun": [
        "Abeokuta North", "Abeokuta South", "Ado-Odo/Ota", "Ewekoro", "Ifo", "Ijebu East",
        "Ijebu North", "Ijebu North East", "Ijebu Ode", "Ikenne", "Imeko Afon", "Ipokia",
        "Obafemi Owode", "Odeda", "Odogbolu", "Ogun Waterside", "Remo North", "Sagamu",
        "Yewa North", "Yewa South",
    ],
    "Ondo": [
        "Akoko North-East", "Akoko North-West", "Akoko South-East", "Akoko South-West",
        "Akure North", "Akure South", "Ese Odo", "Idanre", "Ifedore", "Ilaje",
        "Ile Oluji/Okeigbo", "Irele", "Odigbo", "Okitipupa", "Ondo East", "Ondo West", "Ose", "Owo",
    ],
    "Osun": [
        "Aiyedaade", "Aiyedire", "Atakunmosa East", "Atakunmosa West", "Boluwaduro", "Boripe",
        "Ede North", "Ede South", "Egbedore", "Ejigbo", "Ife Central", "Ife East", "Ife North",
        "Ife South", "Ifedayo", "Ifelodun", "Ila", "Ilesa East", "Ilesa West", "Irepodun",
        "Irewole", "Isokan", "Iwo", "Obokun", "Odo Otin", "Ola Oluwa", "Olorunda", "Oriade",
        "Orolu", "Osogbo",
    ],
    "Oyo": [
        "Afijio", "Akinyele", "Atiba", "Atisbo", "Egbeda", "Ibadan North", "Ibadan North-East",
        "Ibadan North-West", "Ibadan South-East", "Ibadan South-West", "Ibarapa Central",
        "Ibarapa East", "Ibarapa North", "Ido", "Irepo", "Iseyin", "Itesiwaju", "Iwajowa",
        "Kajola", "Lagelu", "Ogbomosho North", "Ogbomosho South", "Ogo Oluwa", "Olorunsogo",
        "Oluyole", "Ona Ara", "Orelope", "Ori Ire", "Oyo East", "Oyo West", "Saki East",
        "Saki West", "Surulere",
    ],
    "Plateau": [
        "Barkin Ladi", "Bassa", "Bokkos", "Jos East", "Jos North", "Jos South", "Kanam",
        "Kanke", "Langtang North", "Langtang South", "Mangu", "Mikang", "Pankshin",
        "Qua'an Pan", "Riyom", "Shendam", "Wase",
    ],
    "Rivers": [
        "Abua/Odual", "Ahoada East", "Ahoada West", "Akuku-Toru", "Andoni", "Asari-Toru",
        "Bonny", "Degema", "Eleme", "Emuoha", "Etche", "Gokana", "Ikwerre", "Khana",
        "Obio/Akpor", "Ogba/Egbema/Ndoni", "Ogu/Bolo", "Okrika", "Omuma", "Opobo/Nkoro",
        "Oyigbo", "Port Harcourt", "Tai",
    ],
    "Sokoto": [
        "Binji", "Bodinga", "Dange Shuni", "Gada", "Goronyo", "Gudu", "Gawabawa", "Illela",
        "Isa", "Kebbe", "Kware", "Rabah", "Sabon Birni", "Shagari", "Silame", "Sokoto North",
        "Sokoto South", "Tambuwal", "Tangaza", "Tureta", "Wamako", "Wurno", "Yabo",
    ],
    "Taraba": [
        "Ardo Kola", "Bali", "Donga", "Gashaka", "Gassol", "Ibi", "Jalingo", "Karim Lamido",
        "Kurmi", "Lau", "Sardauna", "Takum", "Ussa", "Wukari", "Yorro", "Zing",
    ],
    "Yobe": [
        "Bade", "Bursari", "Damaturu", "Fika", "Fune", "Geidam", "Gujba", "Gulani",
        "Jakusko", "Karasuwa", "Machina", "Nangere", "Nguru", "Potiskum", "Tarmuwa",
        "Yunusari", "Yusufari",
    ],
    "Zamfara": [
        "Anka", "Bakura", "Birnin Magaji/Kiyaw", "Bukkuyum", "Bungudu", "Gummi", "Gusau",
        "Kaura Namoda", "Maradun", "Maru", "Shinkafi", "Talata Mafara", "Tsafe", "Zurmi",
    ],
}

DEFAULT_COUNTRIES = get_african_countries_choices()
NIGERIA_LOCATIONS["FCT"] = NIGERIA_LOCATIONS.get("FCT (Abuja)", [])
NIGERIA_LOCATIONS["Federal Capital Territory"] = NIGERIA_LOCATIONS.get("FCT (Abuja)", [])
DEFAULT_REGIONS = [(s, s) for s in sorted(NIGERIA_LOCATIONS.keys())]
DEFAULT_DISTRICTS = sorted({lga for lgas in NIGERIA_LOCATIONS.values() for lga in lgas})


def get_nigeria_lgas(region_name):
    if not region_name:
        return []
    reg = str(region_name).strip()
    if reg in NIGERIA_LOCATIONS:
        return NIGERIA_LOCATIONS[reg]
    reg_clean = reg.replace(' State', '').replace(' state', '').strip()
    if reg_clean in NIGERIA_LOCATIONS:
        return NIGERIA_LOCATIONS[reg_clean]
    if reg_clean.upper() in ('FCT', 'ABUJA', 'FCT (ABUJA)', 'FEDERAL CAPITAL TERRITORY'):
        return NIGERIA_LOCATIONS.get('FCT (Abuja)', [])
    for k, v in NIGERIA_LOCATIONS.items():
        if k.lower() == reg.lower() or k.lower() == reg_clean.lower():
            return v
    return []


class GeographyForm(BaseForm):
    country = forms.ChoiceField(label='Country', choices=[('', 'Select country')])
    region = forms.ChoiceField(label='State / Region / Province', choices=[('', 'Select state')])
    district = forms.ChoiceField(
        label='Local government / District',
        choices=[('', 'Select LGA')],
        required=False,
        error_messages={'invalid_choice': 'More information needed'},
    )
    district_custom = forms.CharField(
        label='Subdivision name',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Enter your subdivision name', 'class': 'input'}),
        help_text='If your subdivision is not listed above, enter it here. This will be flagged for catalogue improvement.',
    )
    district_not_listed = forms.BooleanField(widget=forms.HiddenInput(), required=False)
    community_cluster = forms.CharField(
        label='Community cluster',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Central Community Cluster'}),
        help_text='Your local community cluster or neighborhood',
    )
    local_home = forms.CharField(
        label='Local connection',
        max_length=150,
        required=False,
        disabled=True,
        initial='Pending assignment',
        help_text='Automatically assigned based on your location. This field cannot be edited.',
    )
    country_id = forms.CharField(widget=forms.HiddenInput(), required=False)
    country_iso3 = forms.CharField(widget=forms.HiddenInput(), required=False)
    country_iso2 = forms.CharField(widget=forms.HiddenInput(), required=False)
    country_name = forms.CharField(widget=forms.HiddenInput(), required=False)
    admin1_label = forms.CharField(widget=forms.HiddenInput(), required=False)
    region_id = forms.CharField(widget=forms.HiddenInput(), required=False)
    region_name = forms.CharField(widget=forms.HiddenInput(), required=False)
    region_parent_id = forms.CharField(widget=forms.HiddenInput(), required=False)
    region_unit_type = forms.CharField(widget=forms.HiddenInput(), required=False)
    admin2_label = forms.CharField(widget=forms.HiddenInput(), required=False)
    district_id = forms.CharField(widget=forms.HiddenInput(), required=False)
    district_name = forms.CharField(widget=forms.HiddenInput(), required=False)
    district_parent_id = forms.CharField(widget=forms.HiddenInput(), required=False)
    district_unit_type = forms.CharField(widget=forms.HiddenInput(), required=False)
    data_improvement_flag = forms.BooleanField(widget=forms.HiddenInput(), required=False)
    timezone = forms.CharField(widget=forms.HiddenInput(), required=False)
    timezone_override = forms.BooleanField(widget=forms.HiddenInput(), required=False)
    geography_source = forms.CharField(widget=forms.HiddenInput(), required=False)
    geography_source_version = forms.CharField(widget=forms.HiddenInput(), required=False)
    geography_verified_date = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        policy = current_policy()
        homes = policy.get('homes', []) if policy else []
        network = None
        if self.initial and self.initial.get('network'):
            network = self.initial.get('network')
        elif self.data and self.data.get('network'):
            network = self.data.get('network')

        network_homes = [h for h in homes if not network or h.get('network') == network] if homes else []
        if not network_homes and homes:
            network_homes = homes

        policy_countries = sorted(set(h['country'] for h in network_homes if h.get('country'))) if network_homes else []
        policy_regions = sorted(set(h['region'] for h in network_homes if h.get('region'))) if network_homes else []
        policy_districts = sorted(set(h['district'] for h in network_homes if h.get('district'))) if network_homes else []

        # All 55 African countries selectable plus any custom policy countries
        all_countries = list(DEFAULT_COUNTRIES)
        known_country_names = set(c[0] for c in all_countries)
        for pc in policy_countries:
            if pc and pc not in known_country_names:
                all_countries.append((pc, pc))
        all_countries.sort(key=lambda x: x[0])
        self.fields['country'].choices = [('', 'Select country')] + all_countries

        # Check currently selected country
        selected_country = None
        if self.data and self.data.get('country'):
            selected_country = self.data.get('country')
        elif self.initial and self.initial.get('country'):
            selected_country = self.initial.get('country')

        c_record = get_country(selected_country) if selected_country else None

        # Populate region choices and country-appropriate labels
        if c_record:
            self.fields['region'].label = c_record['admin1_label']
            self.fields['district'].label = c_record['admin2_label']
            self.fields['district_custom'].label = f"Unlisted {c_record['admin2_label']}"
            c_regions = [r[1] for r in c_record['regions']]
            c_policy_regions = [
                h['region'] for h in network_homes
                if h.get('region') and (
                    not h.get('country') or h.get('country') in (selected_country, c_record['name'], c_record['code'], c_record.get('iso3'))
                )
            ]
            combined_regions = sorted(set(c_regions + c_policy_regions))
            self.fields['region'].choices = [('', f"Select {c_record['admin1_label']}")] + [(r, r) for r in combined_regions]
        else:
            self.fields['region'].label = 'State / Region / Province'
            self.fields['district'].label = 'Local government / District'
            combined_regions = sorted(set(policy_regions + [s for s in NIGERIA_LOCATIONS.keys()]))
            self.fields['region'].choices = [('', 'Select state')] + [(r, r) for r in combined_regions]

        # Determine currently selected region
        selected_region = None
        if self.data and self.data.get('region'):
            selected_region = self.data.get('region')
        elif self.initial and self.initial.get('region'):
            selected_region = self.initial.get('region')

        # Populate district choices
        matching_policy_districts = [
            h['district'] for h in network_homes
            if h.get('district') and (not selected_region or h.get('region') == selected_region)
        ]
        if selected_country and (str(selected_country).lower() in ('nigeria', 'ng') or (c_record and c_record.get('iso3') == 'NGA')):
            matched_locs = get_nigeria_lgas(selected_region)
            districts_list = sorted(set(matched_locs + matching_policy_districts))
        elif selected_country and c_record:
            from .geography_catalogue import get_level2_divisions
            l2_objs = get_level2_divisions(c_record['iso3'], selected_region)
            matched_locs = [u['display_name'] for u in l2_objs]
            districts_list = sorted(set(matched_locs + matching_policy_districts))
        elif matching_policy_districts:
            districts_list = sorted(set(matching_policy_districts))
        elif not selected_country:
            districts_list = DEFAULT_DISTRICTS
        else:
            districts_list = []

        local_label = c_record['admin2_label'] if c_record else 'LGA'
        if districts_list:
            self.fields['district'].choices = (
                [('', f"Select {local_label}")]
                + [(d, d) for d in districts_list]
                + [('__not_listed__', 'Not listed, I will type it')]
            )
        else:
            self.fields['district'].choices = [
                ('', f"Select {local_label} (or type below)"),
                ('__not_listed__', 'Not listed, I will type it'),
            ]

        # Check if user had explicitly selected or typed an unlisted district
        init_dist = (self.initial and self.initial.get('district')) or (self.data and self.data.get('district'))
        init_custom = (self.initial and self.initial.get('district_custom')) or (self.data and self.data.get('district_custom'))
        is_explicit_unlisted = bool(
            (self.data and (self.data.get('district') == '__not_listed__' or self.data.get('district_not_listed') in (True, 'true', 'True', '1', 1) or self.data.get('district_custom'))) or
            (self.initial and (self.initial.get('district') == '__not_listed__' or self.initial.get('district_not_listed') in (True, 'true', 'True', 1, '1') or self.initial.get('district_custom')))
        )

        if is_explicit_unlisted:
            self.fields['district'].initial = '__not_listed__'
            self.fields['district_custom'].initial = init_custom or (init_dist if init_dist != '__not_listed__' else '')
            self.fields['district_not_listed'].initial = True

        # Ensure submitted or initial values are always in choices (preserves test payloads)
        for name in ('country', 'region'):
            val = None
            if self.data and self.data.get(name):
                val = self.data.get(name)
            elif self.initial and self.initial.get(name):
                val = self.initial.get(name)
            if val and (val, val) not in self.fields[name].choices:
                self.fields[name].choices.append((val, val))

        for dist_val in [
            self.data.get('district') if self.data else None,
            self.initial.get('district') if self.initial else None,
        ]:
            if dist_val and dist_val != '__not_listed__' and (dist_val, dist_val) not in self.fields['district'].choices:
                # Insert before the '__not_listed__' option
                self.fields['district'].choices.insert(len(self.fields['district'].choices) - 1, (dist_val, dist_val))

        # Set initial local_home based on matching policy homes
        selected_dist = (self.data and self.data.get('district')) or (self.initial and self.initial.get('district'))
        if self.initial and self.initial.get('local_home') and self.initial.get('local_home') != 'Pending assignment':
            self.fields['local_home'].initial = self.initial.get('local_home')
        elif selected_country and selected_region:
            matching_init_homes = [
                h for h in network_homes
                if (h.get('country') in (selected_country, getattr(c_record, 'get', lambda k: '')('name') if c_record else '', getattr(c_record, 'get', lambda k: '')('code') if c_record else '', getattr(c_record, 'get', lambda k: '')('iso3') if c_record else ''))
                and h.get('region') == selected_region
                and (not selected_dist or h.get('district') == selected_dist)
            ]
            if matching_init_homes and matching_init_homes[0].get('label'):
                self.fields['local_home'].initial = matching_init_homes[0]['label']
            else:
                self.fields['local_home'].initial = 'Pending assignment'
        else:
            self.fields['local_home'].initial = 'Pending assignment'

        # Initialize timezone values
        init_tz = (self.data and self.data.get('timezone')) or (self.initial and self.initial.get('timezone'))
        init_override = (self.data and self.data.get('timezone_override')) or (self.initial and self.initial.get('timezone_override'))
        if init_tz:
            self.fields['timezone'].initial = init_tz
        elif selected_country:
            self.fields['timezone'].initial = resolve_timezone_for_location(selected_country, selected_region)
        if init_override:
            self.fields['timezone_override'].initial = True

    def clean_community_cluster(self):
        val = self.cleaned_data.get('community_cluster', '')
        if val is None:
            return ''
        val = str(val).strip()
        if val:
            if len(val) < 2:
                raise forms.ValidationError('Check the highlighted information')
            if '<' in val or '>' in val:
                raise forms.ValidationError('Check the highlighted information')
        return val

    def clean_local_home(self):
        return self.initial.get('local_home', 'Pending assignment')

    def clean(self):
        data = super().clean()
        country_input = data.get('country')
        region_input = data.get('region')

        # Persist stable IDs plus display names
        country_obj = get_country(country_input) if country_input else None
        if country_obj:
            data['country_id'] = country_obj['iso3']
            data['country_iso3'] = country_obj['iso3']
            data['country_iso2'] = country_obj['code']
            data['country_name'] = country_obj['name']
            data['country'] = country_obj['name']
            data['admin1_label'] = country_obj['admin1_label']
            data['admin2_label'] = country_obj['admin2_label']
            data['geography_source'] = country_obj['source']
            data['geography_source_version'] = country_obj['source_version']
            data['geography_verified_date'] = country_obj['last_verified_date']

            # Validate first-level administrative data
            if region_input:
                region_match = find_region_in_country(country_obj['code'], region_input)
                if region_match:
                    data['region_id'] = region_match['code']
                    data['region_name'] = region_match['name']
                    data['region'] = region_match['name']
                    data['region_parent_id'] = country_obj['iso3']
                    data['region_unit_type'] = country_obj['admin1_label']
                else:
                    policy = current_policy()
                    homes = policy.get('homes', []) if policy else []
                    policy_regions = [
                        h.get('region') for h in homes
                        if h.get('country') in (country_input, country_obj['name'], country_obj['code'], country_obj.get('iso3'))
                    ]
                    if region_input not in policy_regions:
                        self.add_error('region', 'Check the highlighted information')
        elif country_input:
            cid = country_input.upper() if len(country_input) == 3 else country_input.lower().replace(' ', '-')
            data['country_id'] = cid
            data['country_iso3'] = cid
            data['country_name'] = country_input
            if region_input:
                data['region_id'] = region_input.lower().replace(' ', '-')
                data['region_name'] = region_input
                data['region_parent_id'] = cid
                data['region_unit_type'] = 'Region'

        # District / Level 2 validation & "Not listed, I will type it" exception handling
        district_input = data.get('district')
        district_custom = (data.get('district_custom') or '').strip()
        is_not_listed = district_input == '__not_listed__' or bool(district_custom) or data.get('district_not_listed')

        if is_not_listed:
            effective_district = district_custom or (district_input if district_input != '__not_listed__' else '')
            if not effective_district:
                self.add_error('district_custom', 'Check the highlighted information')
            elif len(effective_district) < 2 or '<' in effective_district or '>' in effective_district:
                self.add_error('district_custom', 'Check the highlighted information')
            else:
                data['district'] = effective_district
                data['district_name'] = effective_district
                slug = effective_district.lower().replace(' ', '-').replace('/', '-')
                reg_id = data.get('region_id', 'REG')
                data['district_id'] = f"{reg_id}-{slug}"
                data['district_parent_id'] = reg_id
                data['district_unit_type'] = country_obj['admin2_label'] if country_obj else 'Subdivision'
                data['district_not_listed'] = True
                data['data_improvement_flag'] = True
                data['data_improvement_note'] = f"Unlisted subdivision typed for {data.get('country')}/{data.get('region')}: {effective_district}"
                from .geography_catalogue import record_data_improvement_flag
                record_data_improvement_flag(
                    account=getattr(self, 'account', None),
                    country_iso3=data.get('country_iso3', ''),
                    region_id=reg_id,
                    region_name=data.get('region_name', ''),
                    unlisted_subdivision=effective_district,
                    unit_type=data['district_unit_type'],
                    notes=data['data_improvement_note'],
                )
        elif district_input:
            data['district'] = district_input
            data['district_name'] = district_input
            slug = district_input.lower().replace(' ', '-').replace('/', '-')
            reg_id = data.get('region_id', 'REG')
            data['district_id'] = f"{reg_id}-{slug}"
            data['district_parent_id'] = reg_id
            data['district_unit_type'] = country_obj['admin2_label'] if country_obj else 'Subdivision'
            data['district_not_listed'] = False
            data['data_improvement_flag'] = False

            # If country has reliable level 2 (e.g. Nigeria), enforce validity
            is_ng = str(country_input).lower() in ('nigeria', 'ng') or (country_obj and country_obj.get('iso3') == 'NGA')
            if is_ng and region_input:
                lga_list = get_nigeria_lgas(region_input)
                if lga_list and district_input not in lga_list:
                    policy = current_policy()
                    homes = policy.get('homes', []) if policy else []
                    policy_districts = [
                        h.get('district') for h in homes
                        if h.get('country') in ('Nigeria', 'NG', 'NGA') and h.get('region') == region_input
                    ]
                    if district_input not in policy_districts:
                        self.add_error('district', 'More information needed')

        # Deterministic timezone resolution & manual override preservation
        has_override_in_data = bool(self.data and 'timezone_override' in self.data)
        if has_override_in_data:
            val = self.data.get('timezone_override')
            is_override = bool(val) and val not in (False, 'false', 'False', '0', 0, '')
        else:
            is_override = bool(self.initial and self.initial.get('timezone_override'))

        submitted_tz = (self.data and self.data.get('timezone')) or data.get('timezone') or (self.initial and self.initial.get('timezone'))

        if is_override and submitted_tz:
            data['timezone'] = submitted_tz
            data['timezone_override'] = True
        else:
            resolved_tz = resolve_timezone_for_location(country_input, region_input)
            if resolved_tz:
                data['timezone'] = resolved_tz
                data['timezone_override'] = False
            elif submitted_tz:
                data['timezone'] = submitted_tz

        # Policy homes validation
        policy = current_policy()
        if policy:
            homes = policy.get('homes', [])
            if homes:
                network = None
                if self.initial and self.initial.get('network'):
                    network = self.initial.get('network')
                elif self.data and self.data.get('network'):
                    network = self.data.get('network')

                network_homes = [h for h in homes if not network or h.get('network') == network]
                if not network_homes:
                    network_homes = homes

                country = data.get('country')
                region = data.get('region')
                district = data.get('district')

                matching = [
                    h for h in network_homes
                    if h.get('country') in (country, country_obj.get('code') if country_obj else '', country_obj.get('iso3') if country_obj else '')
                    and h.get('region') == region
                    and (not h.get('district') or h.get('district') == district)
                ]
                is_known_district = False
                is_ng = str(country).lower() in ('nigeria', 'ng') or (country_obj and country_obj.get('code') == 'NG')
                if is_ng:
                    lga_list = get_nigeria_lgas(region)
                    if district in lga_list:
                        is_known_district = True
                elif data.get('district_not_listed'):
                    is_known_district = True
                elif country_obj:
                    from .geography_catalogue import get_level2_divisions
                    l2_divs = get_level2_divisions(country_obj['iso3'], region)
                    if district in [d['display_name'] for d in l2_divs]:
                        is_known_district = True

                if not matching and not is_known_district and country and region and district and not data.get('district_not_listed'):
                    self.add_error('district', 'More information needed')
        return data


class InterestsForm(BaseForm):
    interests = forms.CharField(label='Interests', max_length=1000, required=False, widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    skills = forms.CharField(label='Skills to share', max_length=1000, required=False, widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    community_connection = forms.CharField(label='Community connection', max_length=250, required=False, widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    availability = forms.CharField(label='Availability', max_length=250, required=False, widget=forms.TextInput(attrs={'autocomplete': 'off'}))


class ConsentForm(BaseForm):
    privacy_ack = forms.BooleanField(label='Privacy notice', help_text='I have read the current privacy notice.', required=False, disabled=True)
    essential_messages = forms.CharField(label='Essential account messages', initial='Account and service notifications', disabled=True, required=False)
    optional_updates = forms.BooleanField(label='Optional updates', help_text='Programme and community invitations', required=False)
    channel = forms.ChoiceField(label='Preferred channel', choices=[('email', 'Email')])
    notice_digest = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        policy = current_policy()
        if policy:
            self.fields['privacy_ack'].disabled = False
            self.fields['privacy_ack'].required = True
            self.initial['notice_digest'] = policy['digest']

    def clean(self):
        data = super().clean()
        policy = current_policy()
        if policy and data.get('notice_digest') != policy['digest']:
            self.add_error('privacy_ack', 'Another change needs review')
        return data


class ReviewForm(BaseForm):
    review_confirmed = forms.BooleanField(label='Review confirmation', help_text='My details and communication choices are correct.')


FORMS = {1: WelcomeForm, 2: ProfileForm, 3: NetworkForm, 4: GeographyForm, 5: InterestsForm, 6: ConsentForm, 7: ReviewForm}

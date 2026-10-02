"""Forms map to approved v1 ONB controls; sample policy values are not defaults."""
from zoneinfo import available_timezones
import io
from PIL import Image, UnidentifiedImageError
from django import forms
from .onboarding_policy import current_policy
from .locale import LANGUAGES


class BaseForm(forms.Form):
    def __init__(self, *args, account=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account
        for field in self.fields.values():
            field.widget.attrs['class'] = 'input'


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


class NetworkForm(BaseForm):
    eligibility = forms.ChoiceField(label='Age eligibility', choices=[('pending', 'More information needed')])
    network = forms.ChoiceField(label='Proposed network', choices=[('', '—'), ('WGMN', 'WGMN — Good Mother Network'), ('WNNN', 'WNNN')])
    verification_basis = forms.CharField(label='Verification basis', disabled=True, required=False, initial='Pending review')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        policy = current_policy()
        if policy:
            self.fields['eligibility'].choices = [('', '—')] + [(r['code'], r['label']) for r in policy['eligibility']]

    def clean(self):
        data = super().clean()
        policy = current_policy()
        if policy and not any(r['code'] == data.get('eligibility') and r['network'] == data.get('network') for r in policy['eligibility']):
            self.add_error('eligibility', 'More information needed')
        return data
    eligibility_confirmed = forms.BooleanField(label='Confirm eligibility', help_text='I confirm this information is accurate.')


NIGERIA_LOCATIONS = {
    "Anambra": [
        "Aguata", "Anambra East", "Anambra West", "Anaocha", "Awka North", "Awka South",
        "Ayamelum", "Dunukofia", "Ekwusigo", "Idemili North", "Idemili South", "Ihiala",
        "Njikoka", "Nnewi North", "Nnewi South", "Ogbaru", "Onitsha North", "Onitsha South",
        "Orumba North", "Orumba South", "Oyi",
    ],
    "Delta": [
        "Aniocha North", "Aniocha South", "Bomadi", "Burutu", "Ethiope East", "Ethiope West",
        "Ika North East", "Ika South", "Isoko North", "Isoko South", "Ndokwa East", "Ndokwa West",
        "Okpe", "Oshimili North", "Oshimili South", "Patani", "Sapele", "Udu", "Ughelli North",
        "Ughelli South", "Ukwuani", "Uvwie", "Warri North", "Warri South", "Warri South West",
    ],
    "Edo": [
        "Akoko-Edo", "Egor", "Esan Central", "Esan North-East", "Esan South-East", "Esan West",
        "Etsako Central", "Etsako East", "Etsako West", "Igueben", "Ikpoba-Okha", "Orhionmwon",
        "Oredo", "Ovia North-East", "Ovia South-West", "Owan East", "Owan West", "Uhunmwonde",
    ],
    "Enugu": [
        "Aninri", "Awgu", "Enugu East", "Enugu North", "Enugu South", "Ezeagu", "Igbo Etiti",
        "Igbo Eze North", "Igbo Eze South", "Isi Uzo", "Nkanu East", "Nkanu West", "Nsukka",
        "Oji River", "Udenu", "Udi", "Uzo Uwani",
    ],
    "FCT (Abuja)": [
        "Abaji", "Abuja Municipal", "Bwari", "Gwagwalada", "Kuje", "Kwali",
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
    "Lagos": [
        "Agege", "Ajeromi-Ifelodun", "Alimosho", "Amuwo-Odofin", "Apapa", "Badagry", "Epe",
        "Eti-Osa", "Ibeju-Lekki", "Ifako-Ijaiye", "Ikeja", "Ikorodu", "Kosofe", "Lagos Island",
        "Lagos Mainland", "Mushin", "Ojo", "Oshodi-Isolo", "Shomolu", "Surulere",
    ],
    "Ogun": [
        "Abeokuta North", "Abeokuta South", "Ado-Odo/Ota", "Ewekoro", "Ifo", "Ijebu East",
        "Ijebu North", "Ijebu North East", "Ijebu Ode", "Ikenne", "Imeko Afon", "Ipokia",
        "Obafemi Owode", "Odeda", "Odogbolu", "Ogun Waterside", "Remo North", "Sagamu",
        "Yewa North", "Yewa South",
    ],
    "Oyo": [
        "Afijio", "Akinyele", "Atiba", "Atisbo", "Egbeda", "Ibadan North", "Ibadan North-East",
        "Ibadan North-West", "Ibadan South-East", "Ibadan South-West", "Ibarapa Central",
        "Ibarapa East", "Ibarapa North", "Ido", "Irepo", "Iseyin", "Itesiwaju", "Iwajowa",
        "Ogbomosho North", "Ogbomosho South", "Ogo Oluwa", "Olorunsogo", "Oluyole", "Ona Ara",
        "Orelope", "Ori Ire", "Oyo East", "Oyo West", "Saki East", "Saki West", "Surulere",
    ],
    "Rivers": [
        "Abua/Odual", "Ahoada East", "Ahoada West", "Akuku-Toru", "Andoni", "Asari-Toru",
        "Bonny", "Degema", "Eleme", "Emuoha", "Etche", "Gokana", "Ikwerre", "Khana",
        "Obio/Akpor", "Ogba/Egbema/Ndoni", "Ogu/Bolo", "Okrika", "Omuma", "Opobo/Nkoro",
        "Oyigbo", "Port Harcourt", "Tai",
    ],
}

DEFAULT_COUNTRIES = [("Nigeria", "Nigeria")]
DEFAULT_REGIONS = [(s, s) for s in sorted(NIGERIA_LOCATIONS.keys())]
DEFAULT_DISTRICTS = sorted({lga for lgas in NIGERIA_LOCATIONS.values() for lga in lgas})


class GeographyForm(BaseForm):
    country = forms.ChoiceField(label='Country', choices=[('', '—')])
    region = forms.ChoiceField(label='State / FCT', choices=[('', '—')])
    district = forms.ChoiceField(label='LGA', choices=[('', '—')])
    local_home = forms.CharField(label='Local connection', max_length=150, required=False, disabled=True, initial='Pending assignment')

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

        countries = sorted(set(h['country'] for h in network_homes if h.get('country'))) if network_homes else []
        regions = sorted(set(h['region'] for h in network_homes if h.get('region'))) if network_homes else []
        districts = sorted(set(h['district'] for h in network_homes if h.get('district'))) if network_homes else []

        if countries:
            self.fields['country'].choices = [('', '—')] + [(c, c) for c in countries]
            self.fields['region'].choices = [('', '—')] + [(r, r) for r in regions]
            self.fields['district'].choices = [('', '—')] + [(d, d) for d in districts]
        else:
            self.fields['country'].choices = [('', '—')] + DEFAULT_COUNTRIES
            self.fields['region'].choices = [('', '—')] + DEFAULT_REGIONS
            self.fields['district'].choices = [('', '—')] + [(d, d) for d in DEFAULT_DISTRICTS]

        for name in ('country', 'region', 'district'):
            val = None
            if self.data and self.data.get(name):
                val = self.data.get(name)
            elif self.initial and self.initial.get(name):
                val = self.initial.get(name)
            if val and (val, val) not in self.fields[name].choices:
                self.fields[name].choices.append((val, val))

    def clean(self):
        data = super().clean()
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
                    if h.get('country') == country
                    and h.get('region') == region
                    and h.get('district') == district
                ]
                if not matching and country and region and district:
                    self.add_error('district', 'More information needed')
        return data


class InterestsForm(BaseForm):
    interests = forms.CharField(label='Interests', max_length=1000, required=False)
    skills = forms.CharField(label='Skills to share', max_length=1000, required=False)
    community_connection = forms.CharField(label='Community connection', max_length=250, required=False)
    availability = forms.CharField(label='Availability', max_length=250, required=False)


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

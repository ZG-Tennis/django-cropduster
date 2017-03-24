# -*- coding: utf-8 -*-
""" cropduster management command regenerate_crops """

from pydoc import locate

from django.core.management.base import BaseCommand, CommandError

from cropduster.models import Size


class Command(BaseCommand):
    """
    Allows the regenerations for crops taking into account the
    model, cropduster fields and optionally the size slugs
    Usage:
    ./manage.py regenerate_crops -p app.models.MyModel -f field1 -s slug1 slug2
    or to update all field slugs
    ./manage.py regenerate_crops -p app.models.MyModel -f field1 field2
    """

    help = (
        """
        Allows the regenerations for crops taking into account the
        model, cropduster fields and optionally the size slugs
        Usage:
        ./manage.py regenerate_crops -p app.models.MyModel -f field1 -s slug1 slug2
        or to update all field slugs
        ./manage.py regenerate_crops -p app.models.MyModel -f field1 field2
        """
    )

    class_path = ''
    cropduster_fields = []
    size_slugs = []
    cleaned_data = {
        'model': None,
        'fields': None,
        'size_slugs': None
    }

    def add_arguments(self, parser):
        """ adds arguments using python argparse module """

        parser.add_argument(
            '-p', '--objpath',
            action='store',
            dest='class_path',
            default='',
            type=str,
            required=True,
            help='class paths. For instance: -p MyApp.models.MyModel'
        )

        parser.add_argument(
            '-f', '--fields',
            action='store',
            dest='cropduster_fields',
            nargs='+',
            default='',
            type=str,
            required=True,
            help='cropduster field names. For instance: -f img1 img2 img3'
        )

        parser.add_argument(
            '-s', '--sizeslugs',
            action='store',
            dest='size_slugs',
            nargs='*',
            default='',
            type=str,
            required=False,
            help=(
                'Size slugs for instance: -s slug1 slug2 slug3, if not '
                'provided all sizes related with each cropduster field '
                'will be used.'
            )
        )

        parser.add_argument(
            '-P', '--printdata',
            action='store_true',
            dest='print_data',
            default=False,
            required=False,
            help='Prints data about all crops created'
        )

    def parse_options(self, **options):
        """
        Initializes the command attributes using the provided options
        """
        self.class_path = options['class_path']
        self.cropduster_fields = options['cropduster_fields']
        self.size_slugs = options['size_slugs'] if options['size_slugs'] \
            else []
        self.print_data = options['print_data']

    def validate_inputs(self):
        """
        * Validates that all inputs can be imported and/or exists
        * Initializes the cleaned_data dictionary with all validaded data
        """
        model = locate(self.class_path)

        if not model:
            msg = u'{} can not be imported'.format(self.class_path)
            raise CommandError(msg)

        validated_fields = []
        for field in self.cropduster_fields:
            if hasattr(model, field):
                validated_fields.append(field)
            else:
                msg = u'{} does no have {} attribute'.format(model, field)
                self.stdout.write(self.style.WARNING(msg))

        if not validated_fields:
            msg = u'None of provided Fields exists on {}'.format(
                self.class_path)
            raise CommandError(msg)

        validated_size_slugs = []
        if self.size_slugs:
            size_qs = Size.objects.all()
            for slug in self.size_slugs:
                if size_qs.filter(slug=slug):
                    validated_size_slugs.append(slug)
                else:
                    msg = u'No Size with slug = {} exists'.format(slug)
                    self.stdout.write(self.style.WARNING(msg))
            if not validated_size_slugs:
                msg = u'None of the provided Sizes exists'
                raise CommandError(msg)

        self.cleaned_data['model'] = model
        self.cleaned_data['fields'] = validated_fields
        self.cleaned_data['size_slugs'] = validated_size_slugs

    def recreate_crops(self):
        """ Using the cleaned_data tries to recreate crops """

        self.stdout.write("Generating crops...")
        self.crops_generated = 0
        self.crops_not_generated = 0
        qs = self.cleaned_data['model'].objects.all()

        for field in self.cleaned_data['fields']:
            q_filter = field + '__isnull'
            sub_qs = qs.filter(**{q_filter: False})
            for obj in sub_qs.iterator():
                crop_field = getattr(obj, field)
                field_sizes = crop_field.size_set.size_set.all()

                if self.cleaned_data['size_slugs']:
                    field_sizes_slugs = set(
                        field_sizes.values_list('slug', flat=True))
                    field_sizes_slugs = field_sizes_slugs.intersection(
                        self.cleaned_data['size_slugs'])
                    field_sizes = field_sizes.filter(
                        slug__in=field_sizes_slugs)

                for size in field_sizes:
                    try:
                        crop_field.create_thumbnail(size)
                    except Exception:
                        self.crops_not_generated += 1
                    else:
                        if self.print_data:
                            self.stdout.write(
                                'obj.field: {} - obj.id: {} - size.slug: {}'
                                .format(field, obj.id, size.slug)
                            )
                        self.crops_generated += 1

        self.stdout.write(
            "{} crops were generated"
            .format(self.crops_generated)
        )
        self.stdout.write(
            self.style.WARNING(
                "{} crops could not be generated"
                .format(self.crops_not_generated)
            )
        )
        self.stdout.write("Generating proccess finished successfully")

    def handle(self, *args, **options):
        """ Runs the necessary functions to recreate crops """
        self.parse_options(**options)
        self.validate_inputs()
        self.recreate_crops()

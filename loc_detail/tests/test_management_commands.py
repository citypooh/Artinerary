from django.core.management import call_command
from django.test import TestCase
from unittest.mock import patch, MagicMock

from loc_detail.models import PublicArt

class DownsampleImagesCommandTests(TestCase):
    @patch("loc_detail.management.commands.downsample_images.PublicArt")
    def test_downsample_images_dry_run(self, mock_publicart):
        mock_qs = MagicMock()
        mock_publicart.objects.filter.return_value.exclude.return_value = mock_qs
        mock_qs.count.return_value = 2
        mock_qs.iterator.return_value = [
            MagicMock(pk=1, image=MagicMock(name="img1.jpg"), thumbnail=None, downsample_image=MagicMock(return_value=None), make_thumbnail=MagicMock(return_value=None)),
            MagicMock(pk=2, image=MagicMock(name="img2.jpg"), thumbnail=None, downsample_image=MagicMock(return_value=None), make_thumbnail=MagicMock(return_value=None)),
        ]
        call_command("downsample_images", "--dry-run")
        assert mock_publicart.objects.filter.called
        assert mock_qs.exclude.called
        assert mock_qs.count.called
        assert mock_qs.iterator.called

    @patch("loc_detail.management.commands.downsample_images.PublicArt")
    def test_downsample_images_force_and_regen(self, mock_publicart):
        mock_art = MagicMock(pk=1, image=MagicMock(name="img1.jpg"), thumbnail=None)
        mock_art.downsample_image.return_value = MagicMock(name="downsampled.jpg")
        mock_art.make_thumbnail.return_value = MagicMock(name="thumb.jpg")
        mock_qs = MagicMock()
        mock_publicart.objects.filter.return_value.exclude.return_value = mock_qs
        mock_qs.count.return_value = 1
        mock_qs.iterator.return_value = [mock_art]
        call_command("downsample_images", "--force-downsample", "--regenerate-thumbnails")
        assert mock_art.downsample_image.called
        assert mock_art.make_thumbnail.called

class GenerateThumbnailsCommandTests(TestCase):
    @patch("loc_detail.management.commands.generate_thumbnails.PublicArt")
    def test_generate_thumbnails_default(self, mock_publicart):
        mock_art = MagicMock(pk=1, image=MagicMock(name="img1.jpg"), thumbnail=None)
        mock_art.make_thumbnail.return_value = MagicMock(name="thumb.jpg")
        mock_qs = MagicMock()
        mock_publicart.objects.filter.return_value = mock_qs
        mock_qs.filter.return_value = mock_qs
        mock_qs.count.return_value = 1
        mock_qs.iterator.return_value = [mock_art]
        call_command("generate_thumbnails")
        assert mock_art.make_thumbnail.called
        assert mock_art.thumbnail.save.called
        assert mock_art.save.called

    @patch("loc_detail.management.commands.generate_thumbnails.PublicArt")
    def test_generate_thumbnails_force(self, mock_publicart):
        mock_art = MagicMock(pk=1, image=MagicMock(name="img1.jpg"), thumbnail="thumb.jpg")
        mock_art.make_thumbnail.return_value = MagicMock(name="thumb.jpg")
        mock_qs = MagicMock()
        mock_publicart.objects.filter.return_value = mock_qs
        mock_qs.count.return_value = 1
        mock_qs.iterator.return_value = [mock_art]
        call_command("generate_thumbnails", "--force")
        assert mock_art.make_thumbnail.called
        assert mock_art.thumbnail.save.called
        assert mock_art.save.called
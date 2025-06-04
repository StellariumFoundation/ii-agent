import unittest
from unittest.mock import patch, MagicMock, mock_open
import base64
from io import BytesIO

# Import functions to be tested
from src.ii_agent.browser.utils import (
    put_highlight_elements_on_screenshot,
    scale_b64_image,
    calculate_iou,
    is_fully_contained,
    filter_overlapping_elements, # Tested via filter_elements
    sort_elements_by_position,   # Tested via filter_elements
    filter_elements,
    is_pdf_url,
)
# Import models used by these utils
from src.ii_agent.browser.models import InteractiveElement, Rect, Coordinates

# Mock PIL if not available or to control behavior
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = MagicMock()
    ImageDraw = MagicMock()
    ImageFont = MagicMock()

import requests # Added import

class TestBrowserUtils(unittest.TestCase):

    def _create_mock_rect(self, left, top, right, bottom):
        return Rect(left=left, top=top, right=right, bottom=bottom, width=right-left, height=bottom-top)

    def _create_mock_element(self, index, rect_coords, tag="div", weight=1.0, z_index=0, browser_agent_id=""):
        # Simplified element for geometry tests
        return InteractiveElement(
            index=index, tag_name=tag, text=f"el{index}", attributes={}, # Changed text_content to text
            viewport=Coordinates(x=0,y=0), page=Coordinates(x=0,y=0), center=Coordinates(x=0,y=0), # Dummy
            weight=weight, browser_agent_id=browser_agent_id or f"id{index}", rect=self._create_mock_rect(*rect_coords), z_index=z_index
        )

    # Tests for calculate_iou
    def test_calculate_iou_overlapping(self):
        rect1 = self._create_mock_rect(0, 0, 10, 10)
        rect2 = self._create_mock_rect(5, 5, 15, 15)
        # Intersection: (5,5,10,10) -> area 25
        # Union: 100 + 100 - 25 = 175
        # IoU = 25 / 175
        self.assertAlmostEqual(calculate_iou(rect1, rect2), 25 / 175)

    def test_calculate_iou_no_overlap(self):
        rect1 = self._create_mock_rect(0, 0, 10, 10)
        rect2 = self._create_mock_rect(15, 15, 25, 25)
        self.assertEqual(calculate_iou(rect1, rect2), 0.0)

    def test_calculate_iou_identical(self):
        rect1 = self._create_mock_rect(0, 0, 10, 10)
        rect2 = self._create_mock_rect(0, 0, 10, 10)
        self.assertEqual(calculate_iou(rect1, rect2), 1.0)

    def test_calculate_iou_contained(self):
        rect_outer = self._create_mock_rect(0, 0, 20, 20) # Area 400
        rect_inner = self._create_mock_rect(5, 5, 15, 15) # Area 100
        # Intersection is rect_inner area (100)
        # Union is rect_outer area (400)
        # IoU = 100 / 400
        self.assertAlmostEqual(calculate_iou(rect_inner, rect_outer), 100 / 400)


    # Tests for is_fully_contained
    def test_is_fully_contained_true(self):
        rect_outer = self._create_mock_rect(0, 0, 20, 20)
        rect_inner = self._create_mock_rect(5, 5, 15, 15)
        self.assertTrue(is_fully_contained(rect_inner, rect_outer))

    def test_is_fully_contained_false_partial_overlap(self):
        rect1 = self._create_mock_rect(0, 0, 10, 10)
        rect2 = self._create_mock_rect(5, 5, 15, 15)
        self.assertFalse(is_fully_contained(rect1, rect2))
        self.assertFalse(is_fully_contained(rect2, rect1))

    def test_is_fully_contained_false_no_overlap(self):
        rect1 = self._create_mock_rect(0, 0, 10, 10)
        rect2 = self._create_mock_rect(15, 15, 25, 25)
        self.assertFalse(is_fully_contained(rect1, rect2))

    # Tests for filter_elements (which uses sort and filter_overlapping)
    def test_filter_elements_sorts_by_position(self):
        # Top-to-bottom, then left-to-right
        el1 = self._create_mock_element(0, (10, 10, 20, 20)) # Top-left
        el2 = self._create_mock_element(1, (30, 10, 40, 20)) # Top-right
        el3 = self._create_mock_element(2, (10, 30, 20, 40)) # Bottom-left

        elements = [el2, el3, el1] # Unsorted
        filtered = filter_elements(elements, iou_threshold=0.1) # Low threshold to not filter these non-overlapping

        self.assertEqual(len(filtered), 3)
        self.assertEqual(filtered[0].rect.left, 10) # el1
        self.assertEqual(filtered[0].index, 0) # Original index preserved if not filtered
        self.assertEqual(filtered[1].rect.left, 30) # el2
        self.assertEqual(filtered[1].index, 1)
        self.assertEqual(filtered[2].rect.top, 30)   # el3
        self.assertEqual(filtered[2].index, 2)
        # Note: filter_elements re-assigns element.index after sorting, so we'd expect 0, 1, 2
        # The provided sort_elements_by_position re-indexes.
        self.assertEqual([el.index for el in filtered], [0,1,2])


    def test_filter_elements_removes_high_iou_overlap(self):
        # el1 is larger and will be sorted first
        el1 = self._create_mock_element(0, (0, 0, 100, 100), weight=1.0)
        # el2 significantly overlaps with el1
        el2 = self._create_mock_element(1, (10, 10, 110, 110), weight=0.9)

        # IoU of el1 and el2: intersection (10,10,100,100) area 90*90=8100
        # Union: 10000 + 10000 - 8100 = 11900. IoU = 8100/11900 ~ 0.68

        elements = [el1, el2]
        # With high threshold, el2 (which comes after el1 due to sort by area) should be removed
        filtered = filter_elements(elements, iou_threshold=0.5)
        self.assertEqual(len(filtered), 1)
        self.assertIs(filtered[0], el1) # el1 (larger area) should be kept

    # Tests for is_pdf_url
    @patch('requests.head')
    @patch('requests.get')
    def test_is_pdf_url_by_extension(self, mock_get, mock_head):
        self.assertTrue(is_pdf_url("http://example.com/document.pdf"))
        mock_head.assert_not_called()
        mock_get.assert_not_called()

    @patch('requests.head')
    @patch('requests.get')
    def test_is_pdf_url_by_head_content_type(self, mock_get, mock_head):
        mock_head_response = MagicMock()
        mock_head_response.headers = {"Content-Type": "application/pdf; charset=utf-8"}
        mock_head.return_value = mock_head_response

        self.assertTrue(is_pdf_url("http://example.com/document"))
        mock_head.assert_called_once()
        mock_get.assert_not_called()

    @patch('requests.head')
    @patch('requests.get')
    def test_is_pdf_url_by_get_content_type(self, mock_get, mock_head):
        mock_head_response = MagicMock()
        mock_head_response.headers = {"Content-Type": "text/html"} # Head doesn't say PDF
        mock_head.return_value = mock_head_response

        mock_get_response = MagicMock()
        mock_get_response.headers = {"Content-Type": "application/pdf"}
        mock_get.return_value = mock_get_response

        self.assertTrue(is_pdf_url("http://example.com/dynamic_pdf"))
        mock_head.assert_called_once()
        mock_get.assert_called_once() # GET is called as fallback

    @patch('requests.head')
    @patch('requests.get')
    def test_is_pdf_url_not_pdf(self, mock_get, mock_head):
        mock_head_response = MagicMock(); mock_head_response.headers = {"Content-Type": "text/html"}
        mock_head.return_value = mock_head_response
        mock_get_response = MagicMock(); mock_get_response.headers = {"Content-Type": "text/plain"}
        mock_get.return_value = mock_get_response

        self.assertFalse(is_pdf_url("http://example.com/not_a_pdf"))

    @patch('requests.head', side_effect=requests.exceptions.RequestException("Network Error"))
    @patch('requests.get') # Won't be called if head fails this way
    def test_is_pdf_url_request_exception(self, mock_get, mock_head):
        self.assertFalse(is_pdf_url("http://example.com/network_issue"))
        mock_get.assert_not_called() # If head fails, get shouldn't be called.


    # Tests for put_highlight_elements_on_screenshot and scale_b64_image are more involved
    # due to mocking PIL. Focus on checking if they call PIL methods correctly.

    @patch('src.ii_agent.browser.utils.Image.open')
    @patch('src.ii_agent.browser.utils.ImageDraw.Draw')
    @patch('src.ii_agent.browser.utils.ImageFont.truetype') # Assuming custom font path is valid
    @patch('base64.b64decode')
    @patch('base64.b64encode')
    def test_put_highlight_elements_on_screenshot_calls_pil(
        self, mock_b64encode, mock_b64decode, mock_font_truetype, mock_imagedraw, mock_image_open
    ):
        mock_pil_image = MagicMock(spec=Image.Image)
        mock_pil_image.size = (800, 600)
        mock_image_open.return_value = mock_pil_image
        mock_draw_instance = MagicMock(spec=ImageDraw.ImageDraw)
        mock_imagedraw.return_value = mock_draw_instance
        mock_font_instance = MagicMock(spec=ImageFont.FreeTypeFont)
        mock_font_truetype.return_value = mock_font_instance

        # Mock textbbox to return sensible values
        mock_draw_instance.textbbox.return_value = (0, 0, 10, 10) # left, top, right, bottom

        mock_b64decode.return_value = b"decoded_image_data"
        mock_b64encode.return_value = b"reencoded_highlighted_data"

        elements = {
            0: self._create_mock_element(0, (10,10,60,30), tag="button"),
            1: self._create_mock_element(1, (100,100,150,120), tag="input")
        }
        screenshot_b64 = "original_screenshot_data"

        result = put_highlight_elements_on_screenshot(elements, screenshot_b64)

        mock_b64decode.assert_called_once_with(screenshot_b64)
        mock_image_open.assert_called_once() # Arg is BytesIO(decoded_data)
        mock_imagedraw.assert_called_once_with(mock_pil_image)

        self.assertTrue(mock_draw_instance.rectangle.call_count >= 2) # At least one for each element box + label bg
        self.assertTrue(mock_draw_instance.text.call_count >= 2)     # At least one for each element label

        mock_pil_image.save.assert_called_once()
        mock_b64encode.assert_called_once()
        self.assertEqual(result, "reencoded_highlighted_data") # Decoded from bytes

    @patch('src.ii_agent.browser.utils.Image.open')
    @patch('base64.b64decode')
    @patch('base64.b64encode')
    def test_scale_b64_image_calls_pil_resize(
        self, mock_b64encode, mock_b64decode, mock_image_open
    ):
        mock_pil_image = MagicMock(spec=Image.Image)
        mock_pil_image.size = (1000, 800)
        mock_resized_image = MagicMock(spec=Image.Image)
        mock_pil_image.resize.return_value = mock_resized_image
        mock_image_open.return_value = mock_pil_image

        mock_b64decode.return_value = b"decoded_image_data_scale"
        mock_b64encode.return_value = b"reencoded_scaled_data"

        original_b64 = "original_for_scale"
        scale_factor = 0.5
        result = scale_b64_image(original_b64, scale_factor)

        mock_b64decode.assert_called_once_with(original_b64)
        mock_image_open.assert_called_once()
        mock_pil_image.resize.assert_called_once_with((500, 400), Image.LANCZOS)
        mock_resized_image.save.assert_called_once()
        mock_b64encode.assert_called_once()
        self.assertEqual(result, "reencoded_scaled_data")


if __name__ == "__main__":
    unittest.main()

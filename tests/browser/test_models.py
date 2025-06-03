import unittest
from src.ii_agent.browser.models import (
    TabInfo,
    Coordinates,
    Rect,
    InteractiveElement,
    BrowserError,
    URLNotAllowedError,
    Viewport,
    InteractiveElementsData,
    BrowserState,
)

class TestBrowserModels(unittest.TestCase):

    def test_tab_info_instantiation(self):
        tab = TabInfo(page_id=1, url="http://example.com", title="Example")
        self.assertEqual(tab.page_id, 1)
        self.assertEqual(tab.url, "http://example.com")
        self.assertEqual(tab.title, "Example")

    def test_coordinates_instantiation(self):
        coords_full = Coordinates(x=10, y=20, width=100, height=50)
        self.assertEqual(coords_full.x, 10)
        self.assertEqual(coords_full.width, 100)

        coords_minimal = Coordinates(x=5, y=15)
        self.assertEqual(coords_minimal.x, 5)
        self.assertIsNone(coords_minimal.width) # Default is None

    def test_rect_instantiation(self):
        rect = Rect(left=0, top=10, right=100, bottom=110, width=100, height=100)
        self.assertEqual(rect.left, 0)
        self.assertEqual(rect.width, 100)

    def test_interactive_element_instantiation(self):
        viewport_coords = Coordinates(x=0,y=0,width=800,height=600)
        page_coords = Coordinates(x=10,y=20,width=100,height=30)
        center_coords = Coordinates(x=60,y=35)
        element_rect = Rect(left=10,top=20,right=110,bottom=50,width=100,height=30)

        element = InteractiveElement(
            index=1,
            tag_name="button",
            text_content="Click Me", # Pydantic will map text_content to text if alias is used for input
            attributes={"id": "btn1", "class": "submit"},
            viewport=viewport_coords,
            page=page_coords,
            center=center_coords,
            weight=0.85,
            browser_agent_id="agent-id-1",
            input_type="submit", # Optional
            rect=element_rect,
            z_index=2
        )
        self.assertEqual(element.index, 1)
        self.assertEqual(element.tag_name, "button")
        self.assertEqual(element.text, "Click Me") # Access via 'text' field name
        self.assertEqual(element.input_type, "submit")
        self.assertEqual(element.browser_agent_id, "agent-id-1")

        # Test camelCase alias loading if data came from an external source using camelCase
        # For direct instantiation, Pythonic names are used.
        # If we were loading from a dict:
        data_camel_case = {
            "index": 2, "tagName": "input", "textContent": "User",
            "attributes": {}, "viewport": {"x":0, "y":0}, "page": {"x":0,"y":0},
            "center": {"x":0,"y":0}, "weight": 0.7, "browserAgentId": "id2",
            "inputType": "text",
            "rect": {"left":0,"top":0,"right":10,"bottom":10,"width":10,"height":10},
            "zIndex": 1
        }
        element_from_camel = InteractiveElement.model_validate(data_camel_case)
        self.assertEqual(element_from_camel.tag_name, "input")
        self.assertEqual(element_from_camel.text_content, "User") # text_content is an alias for text
        self.assertEqual(element_from_camel.browser_agent_id, "id2")


    def test_viewport_instantiation_defaults(self):
        vp = Viewport() # Uses default factory
        self.assertEqual(vp.width, 1024)
        self.assertEqual(vp.height, 768)
        self.assertEqual(vp.scroll_x, 0)
        self.assertEqual(vp.scroll_y, 0)
        self.assertEqual(vp.device_pixel_ratio, 1.0)

    def test_viewport_instantiation_with_values(self):
        vp = Viewport(width=800, height=600, scroll_x=10, scroll_y=20, device_pixel_ratio=1.5)
        self.assertEqual(vp.width, 800)
        self.assertEqual(vp.scroll_y, 20)
        self.assertEqual(vp.device_pixel_ratio, 1.5)

    def test_interactive_elements_data_instantiation(self):
        vp = Viewport()
        el = InteractiveElement(
            index=0, tag_name="a", text="link", attributes={}, viewport=Coordinates(x=0,y=0),
            page=Coordinates(x=0,y=0), center=Coordinates(x=0,y=0), weight=1.0,
            browser_agent_id="aid1", rect=Rect(left=0,top=0,right=1,bottom=1,width=1,height=1), z_index=0
        )
        data = InteractiveElementsData(viewport=vp, elements=[el])
        self.assertIs(data.viewport, vp)
        self.assertEqual(len(data.elements), 1)
        self.assertIs(data.elements[0], el)

    def test_browser_state_instantiation_defaults(self):
        state = BrowserState(url="http://example.com", tabs=[])
        self.assertEqual(state.url, "http://example.com")
        self.assertEqual(state.tabs, [])
        self.assertIsInstance(state.viewport, Viewport) # Default factory
        self.assertEqual(state.viewport.width, 1024) # Check default from Viewport
        self.assertIsNone(state.screenshot_with_highlights)
        self.assertIsNone(state.screenshot)
        self.assertEqual(state.interactive_elements, {}) # Default factory

    def test_browser_state_instantiation_with_values(self):
        vp = Viewport(width=100, height=100)
        tab = TabInfo(page_id=0, url="url", title="title")
        el = InteractiveElement(
            index=0, tag_name="a", text="link", attributes={}, viewport=Coordinates(x=0,y=0),
            page=Coordinates(x=0,y=0), center=Coordinates(x=0,y=0), weight=1.0,
            browser_agent_id="aid1", rect=Rect(left=0,top=0,right=1,bottom=1,width=1,height=1), z_index=0
        )
        state = BrowserState(
            url="http://test.com",
            tabs=[tab],
            viewport=vp,
            screenshot_with_highlights="highlight_data",
            screenshot="raw_data",
            interactive_elements={0: el}
        )
        self.assertEqual(state.url, "http://test.com")
        self.assertEqual(state.tabs[0].title, "title")
        self.assertEqual(state.viewport.width, 100)
        self.assertEqual(state.interactive_elements[0].tag_name, "a")

    def test_custom_exceptions(self):
        with self.assertRaises(BrowserError):
            raise BrowserError("A browser error occurred")

        with self.assertRaises(BrowserError): # URLNotAllowedError is a subclass of BrowserError
            raise URLNotAllowedError("URL is not allowed")

        with self.assertRaises(URLNotAllowedError):
            raise URLNotAllowedError("URL specifically not allowed")

if __name__ == "__main__":
    unittest.main()

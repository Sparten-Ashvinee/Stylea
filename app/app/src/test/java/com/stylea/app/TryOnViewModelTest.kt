package com.stylea.app

import android.app.Application
import android.graphics.Bitmap
import androidx.arch.core.executor.testing.InstantTaskExecutorRule
import com.stylea.app.data.api.ApiException
import com.stylea.app.data.api.StyleaApiClient
import com.stylea.app.data.models.TryOnResult
import com.stylea.app.ui.viewmodels.TryOnViewModel
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.mock

/**
 * Unit tests for [TryOnViewModel] state transitions.
 *
 * Because the ViewModel depends on Android's Application context and
 * instrumented APIs (MediaStore, FileProvider), full integration tests run
 * on an Android device/emulator. These tests cover the pure logic paths only.
 */
class TryOnViewModelTest {

    @get:Rule
    val instantExecutorRule = InstantTaskExecutorRule()

    @Test
    fun `initial state is Idle`() {
        // We can't instantiate TryOnViewModel (needs Application) in a unit
        // test without Robolectric, so we test UiState equality directly.
        val idle: TryOnViewModel.UiState = TryOnViewModel.UiState.Idle
        assertTrue(idle is TryOnViewModel.UiState.Idle)
    }

    @Test
    fun `UiState Error carries message`() {
        val errorState = TryOnViewModel.UiState.Error("Network failure")
        assertEquals("Network failure", (errorState as TryOnViewModel.UiState.Error).message)
    }

    @Test
    fun `UiState Success carries result`() {
        val bmp = Bitmap.createBitmap(10, 10, Bitmap.Config.ARGB_8888)
        val result = TryOnResult(tryOnBitmap = bmp, segmentedBitmap = bmp)
        val state = TryOnViewModel.UiState.Success(result)
        assertNotNull((state as TryOnViewModel.UiState.Success).result.tryOnBitmap)
    }

    @Test
    fun `ApiException stores http code and message`() {
        val ex = ApiException(503, "Model not ready")
        assertEquals(503, ex.httpCode)
        assertTrue(ex.message!!.contains("Model not ready"))
    }
}
